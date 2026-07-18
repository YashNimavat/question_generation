import pytest

from config import secrets as secrets_module
from core.enums import QuestionStatus
from db.connection import get_connection
from db.repositories import questions_repo
from services import dedup
from tests.factories import FakeEmbeddingProvider, FakeVectorStore, make_embedding_result, make_mcq_question

QUERY_VECTOR = [1.0, 0.0]
IDENTICAL_VECTOR = [1.0, 0.0]  # cosine distance 0.0 -- hard duplicate
NEAR_VECTOR = [0.9, 0.43589]  # cosine distance ~0.10 -- soft flag
FAR_VECTOR = [0.0, 1.0]  # cosine distance 1.0 -- not similar


def _store_with(vector: list[float], question_id: str, question_version: int, topic: str) -> FakeVectorStore:
    store = FakeVectorStore()
    store.add(
        ids=[f"{question_id}_{question_version}"],
        vectors=[vector],
        metadata=[{"question_id": question_id, "question_version": question_version, "topic": topic}],
    )
    return store


def test_check_similarity_hard_duplicate_against_approved(db_path):
    existing = make_mcq_question(id="q1", version=1, topic="geography", status=QuestionStatus.APPROVED)
    questions_repo.insert(existing, db_path=db_path)
    store = _store_with(IDENTICAL_VECTOR, "q1", 1, "geography")

    result = dedup.check_similarity(QUERY_VECTOR, topic="geography", vector_store=store, db_path=db_path)

    assert result.is_duplicate is True
    assert result.is_flagged is False
    assert result.match.question_id == "q1"
    assert result.match.score == pytest.approx(0.0, abs=1e-6)


def test_check_similarity_soft_flag_against_pending_review(db_path):
    existing = make_mcq_question(id="q1", version=1, topic="geography", status=QuestionStatus.PENDING_REVIEW)
    questions_repo.insert(existing, db_path=db_path)
    store = _store_with(NEAR_VECTOR, "q1", 1, "geography")

    result = dedup.check_similarity(QUERY_VECTOR, topic="geography", vector_store=store, db_path=db_path)

    assert result.is_duplicate is False
    assert result.is_flagged is True
    assert result.match.question_id == "q1"
    assert result.match.score == pytest.approx(0.10, abs=1e-3)


def test_check_similarity_no_match_when_not_similar_enough(db_path):
    existing = make_mcq_question(id="q1", version=1, topic="geography", status=QuestionStatus.APPROVED)
    questions_repo.insert(existing, db_path=db_path)
    store = _store_with(FAR_VECTOR, "q1", 1, "geography")

    result = dedup.check_similarity(QUERY_VECTOR, topic="geography", vector_store=store, db_path=db_path)

    assert result.is_duplicate is False
    assert result.is_flagged is False
    assert result.match is None


def test_check_similarity_ignores_matches_outside_comparison_pool(db_path):
    for status in (QuestionStatus.GENERATED, QuestionStatus.REJECTED):
        existing = make_mcq_question(id=f"q_{status.value}", version=1, topic="geography", status=status)
        questions_repo.insert(existing, db_path=db_path)

    store = FakeVectorStore()
    store.add(
        ids=["q_generated_1", "q_rejected_1"],
        vectors=[IDENTICAL_VECTOR, IDENTICAL_VECTOR],
        metadata=[
            {"question_id": "q_generated", "question_version": 1, "topic": "geography"},
            {"question_id": "q_rejected", "question_version": 1, "topic": "geography"},
        ],
    )

    result = dedup.check_similarity(QUERY_VECTOR, topic="geography", vector_store=store, db_path=db_path)

    assert result.is_duplicate is False
    assert result.is_flagged is False
    assert result.match is None


def test_check_similarity_returns_no_match_when_store_is_empty(db_path):
    result = dedup.check_similarity(
        QUERY_VECTOR, topic="geography", vector_store=FakeVectorStore(), db_path=db_path
    )

    assert result == dedup.DedupResult()


def test_embed_stem_logs_metadata_and_returns_vector(db_path):
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])])

    vector = dedup.embed_stem("What is the capital of France?", embedding_provider=embedding_provider, db_path=db_path)

    assert vector == [1.0, 0.0]
    assert embedding_provider.calls == [
        {"texts": ["What is the capital of France?"], "model": "embed-english-v3.0", "input_type": "search_document"}
    ]
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM metadata_logs").fetchall()
    assert len(rows) == 1
    assert rows[0]["operation_type"] == "embedding"


def test_embed_stem_returns_none_when_no_embedding_provider_configured(db_path, tmp_path, monkeypatch):
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('groq_api_key = "test-key"\n')
    monkeypatch.setattr(secrets_module, "SECRETS_PATH", secrets_path)

    vector = dedup.embed_stem("What is the capital of France?", db_path=db_path)

    assert vector is None
    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM metadata_logs").fetchone()[0]
    assert count == 0


def test_batch_near_duplicate_rate_returns_none_without_embedding_provider(db_path, tmp_path, monkeypatch):
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('groq_api_key = "test-key"\n')
    monkeypatch.setattr(secrets_module, "SECRETS_PATH", secrets_path)

    rate = dedup.batch_near_duplicate_rate(["stem one", "stem two"], db_path=db_path)

    assert rate is None
    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM metadata_logs").fetchone()[0]
    assert count == 0


def test_batch_near_duplicate_rate_returns_zero_for_a_single_stem(db_path):
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[QUERY_VECTOR])])

    rate = dedup.batch_near_duplicate_rate(
        ["only stem"], embedding_provider=embedding_provider, db_path=db_path
    )

    assert rate == 0.0
    assert embedding_provider.calls == []  # single-stem batches never need an embed call


def test_batch_near_duplicate_rate_scoped_to_the_batch_only(db_path):
    # stem 0 and stem 1 are near-duplicates of each other (distance ~0.10, under the
    # default 0.15 soft threshold); stem 2 is unrelated to both.
    embedding_provider = FakeEmbeddingProvider(
        [make_embedding_result(vectors=[QUERY_VECTOR, NEAR_VECTOR, FAR_VECTOR])]
    )

    rate = dedup.batch_near_duplicate_rate(
        ["stem a", "stem a near-duplicate", "stem b unrelated"],
        embedding_provider=embedding_provider,
        db_path=db_path,
    )

    assert rate == pytest.approx(2 / 3)
    assert embedding_provider.calls == [
        {
            "texts": ["stem a", "stem a near-duplicate", "stem b unrelated"],
            "model": "embed-english-v3.0",
            "input_type": "search_document",
        }
    ]
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM metadata_logs").fetchall()
    assert len(rows) == 1
    assert rows[0]["operation_type"] == "embedding"


def test_batch_near_duplicate_rate_ignores_persisted_pool(db_path):
    # An identical-vector "existing" question is in the approved pool, but
    # batch_near_duplicate_rate has no vector_store/topic param at all -- it can only
    # ever compare within the batch passed to it, never against history.
    existing = make_mcq_question(id="q1", version=1, topic="geography", status=QuestionStatus.APPROVED)
    questions_repo.insert(existing, db_path=db_path)
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[QUERY_VECTOR, FAR_VECTOR])])

    rate = dedup.batch_near_duplicate_rate(
        ["new stem a", "new stem b"], embedding_provider=embedding_provider, db_path=db_path
    )

    assert rate == 0.0


def test_record_question_embedding_adds_to_vector_store():
    store = FakeVectorStore()

    dedup.record_question_embedding(
        question_id="q1", question_version=2, topic="geography", vector=[1.0, 0.0], vector_store=store
    )

    assert store.added == [
        {
            "ids": ["q1_2"],
            "vectors": [[1.0, 0.0]],
            "metadata": [{"question_id": "q1", "question_version": 2, "topic": "geography"}],
        }
    ]
