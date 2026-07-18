import json

import pytest

from config import secrets as secrets_module
from core.enums import QuestionStatus, Source
from db.connection import get_connection
from db.repositories import documents_repo, metadata_repo, questions_repo
from services.generation import GenerationError, generate_mcq
from tests.factories import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeVectorStore,
    make_document,
    make_embedding_result,
    make_llm_result,
)

VALID_MCQ_JSON = json.dumps(
    {
        "stem": "What is the capital of France?",
        "options": [
            {"id": "A", "text": "Paris", "is_correct": True},
            {"id": "B", "text": "Lyon", "is_correct": False},
            {"id": "C", "text": "Nice", "is_correct": False},
            {"id": "D", "text": "Marseille", "is_correct": False},
        ],
        "correct_option_id": "A",
        "explanation": "Paris has been the capital of France since the 10th century.",
    }
)


def test_generate_mcq_happy_path_persists_question_and_metadata(db_path):
    provider = FakeLLMProvider([make_llm_result(text=VALID_MCQ_JSON)])

    question = generate_mcq(
        topic="geography", difficulty="easy", provider=provider, model="llama-3.3-70b-versatile", db_path=db_path
    )

    assert question.status == QuestionStatus.GENERATED
    assert question.source == Source.TOPIC
    assert question.stem == "What is the capital of France?"
    assert question.payload.correct_option_id == "A"
    assert len(provider.calls) == 1

    stored = questions_repo.get(question.id, question.version, db_path=db_path)
    assert stored == question

    metadata_record = metadata_repo.get(question.generation_metadata_id, db_path=db_path)
    assert metadata_record is not None
    assert metadata_record.prompt_version == "mcq_v1"


def test_generate_mcq_retries_once_on_malformed_json_then_succeeds(db_path):
    provider = FakeLLMProvider(
        [
            make_llm_result(text="not json"),
            make_llm_result(text=VALID_MCQ_JSON),
        ]
    )

    question = generate_mcq(topic="geography", difficulty="easy", provider=provider, db_path=db_path)

    assert question.stem == "What is the capital of France?"
    assert len(provider.calls) == 2


def test_generate_mcq_fails_after_two_malformed_attempts(db_path):
    provider = FakeLLMProvider(
        [
            make_llm_result(text="not json"),
            make_llm_result(text="still not json"),
        ]
    )

    with pytest.raises(GenerationError):
        generate_mcq(topic="geography", difficulty="easy", provider=provider, db_path=db_path)

    assert len(provider.calls) == 2
    assert questions_repo.list_questions(topic="geography", db_path=db_path) == []

    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM metadata_logs").fetchone()[0]
    assert count == 2


def _vector_store_with_chunks(document_id: str) -> FakeVectorStore:
    vector_store = FakeVectorStore()
    vector_store.add(
        ids=[f"{document_id}_0", f"{document_id}_1"],
        vectors=[[1.0, 0.0], [0.0, 1.0]],
        metadata=[
            {
                "document_id": document_id,
                "chunk_index": 0,
                "text": "Paris has been the capital of France since the 10th century.",
                "start_char": 0,
                "end_char": 60,
            },
            {
                "document_id": document_id,
                "chunk_index": 1,
                "text": "France is located in Western Europe.",
                "start_char": 60,
                "end_char": 97,
            },
        ],
    )
    return vector_store


def test_generate_mcq_grounded_in_document_persists_rag_usage_and_source(db_path):
    documents_repo.insert(make_document(id="doc1"), db_path=db_path)
    provider = FakeLLMProvider([make_llm_result(text=VALID_MCQ_JSON)])
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])])
    vector_store = _vector_store_with_chunks("doc1")

    question = generate_mcq(
        topic="geography",
        difficulty="easy",
        document_id="doc1",
        provider=provider,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        db_path=db_path,
    )

    assert question.source == Source.DOCUMENT
    assert question.document_id == "doc1"

    metadata_record = metadata_repo.get(question.generation_metadata_id, db_path=db_path)
    assert metadata_record.prompt_version == "mcq_grounded_v1"
    assert metadata_record.rag_usage == {
        "document_id": "doc1",
        "chunk_ids": ["doc1_0", "doc1_1"],
    }

    # the grounded prompt must have received the retrieved chunk text
    sent_prompt = provider.calls[0]["messages"][1].content
    assert "Paris has been the capital of France since the 10th century." in sent_prompt

    # the query-side embedding call must be logged too (generation + embedding rows)
    with get_connection(db_path) as conn:
        operation_types = {
            row["operation_type"]
            for row in conn.execute("SELECT operation_type FROM metadata_logs").fetchall()
        }
    assert operation_types == {"generation", "embedding"}


def test_generate_mcq_without_document_id_leaves_rag_usage_none(db_path):
    provider = FakeLLMProvider([make_llm_result(text=VALID_MCQ_JSON)])

    question = generate_mcq(topic="geography", difficulty="easy", provider=provider, db_path=db_path)

    metadata_record = metadata_repo.get(question.generation_metadata_id, db_path=db_path)
    assert metadata_record.rag_usage is None
    assert metadata_record.prompt_version == "mcq_v1"
    assert question.document_id is None


def test_generate_mcq_grounded_raises_when_no_chunks_found(db_path):
    provider = FakeLLMProvider([])
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])])
    vector_store = FakeVectorStore()

    with pytest.raises(GenerationError, match="No relevant chunks found"):
        generate_mcq(
            topic="geography",
            difficulty="easy",
            document_id="doc1",
            provider=provider,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            db_path=db_path,
        )

    assert provider.calls == []


def test_generate_mcq_grounded_passes_top_k_through_to_retrieval(db_path):
    documents_repo.insert(make_document(id="doc1"), db_path=db_path)
    provider = FakeLLMProvider([make_llm_result(text=VALID_MCQ_JSON)])
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])])
    vector_store = _vector_store_with_chunks("doc1")

    generate_mcq(
        topic="geography",
        difficulty="easy",
        document_id="doc1",
        top_k=1,
        provider=provider,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        db_path=db_path,
    )

    assert vector_store.queried[0]["top_k"] == 1


def test_generate_mcq_grounded_wraps_missing_embedding_key_as_generation_error(db_path, tmp_path, monkeypatch):
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('groq_api_key = "test-key"\n')
    monkeypatch.setattr(secrets_module, "SECRETS_PATH", secrets_path)

    provider = FakeLLMProvider([])

    with pytest.raises(GenerationError, match="Embedding provider unavailable"):
        generate_mcq(
            topic="geography",
            difficulty="easy",
            document_id="doc1",
            provider=provider,
            vector_store=FakeVectorStore(),
            db_path=db_path,
        )

    assert provider.calls == []
