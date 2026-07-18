from pathlib import Path

from pydantic import BaseModel

from config.settings import settings
from core.enums import OperationType, QuestionStatus
from db.connection import DEFAULT_DB_PATH
from db.repositories import questions_repo
from embeddings.base import EmbeddingProvider
from embeddings.registry import get_embedding_provider
from metadata.logger import log_call
from rag.vector_store import ChromaVectorStore, VectorStore

COLLECTION_NAME = "questions"
COLLECTION_METADATA = {"hnsw:space": "cosine"}

# Only questions that are still live candidates for the dataset count as existing
# "duplicates to check against" -- a rejected question (including one rejected as a
# duplicate itself) is not compared against, per the "approved + pending_review" pool.
COMPARISON_STATUSES = {QuestionStatus.APPROVED, QuestionStatus.PENDING_REVIEW}


class DuplicateMatch(BaseModel):
    question_id: str
    question_version: int
    score: float  # cosine distance against the questions collection; lower = more similar


class DedupResult(BaseModel):
    is_duplicate: bool = False  # above the hard threshold -- auto-reject
    is_flagged: bool = False  # above the soft threshold -- surface to SME, don't reject
    match: DuplicateMatch | None = None


def _default_vector_store() -> VectorStore:
    return ChromaVectorStore(
        persist_dir=settings.chroma_persist_dir,
        collection_name=COLLECTION_NAME,
        metadata=COLLECTION_METADATA,
    )


def embed_stem(
    stem: str,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[float] | None:
    """Embeds a question stem for dedup comparison, logging the call like every other
    embedding operation. Returns None (skipping dedup) if no embedding provider is
    configured -- a visitor with only a Groq key can still generate questions, they
    just don't get duplicate-checked (see docs/DECISIONS.md, Slice 8)."""
    try:
        embedding_provider = embedding_provider or get_embedding_provider()
    except ValueError:
        return None
    embedding_model = embedding_model or settings.default_embedding_model

    result = embedding_provider.embed([stem], model=embedding_model)
    log_call(
        operation_type=OperationType.EMBEDDING,
        provider=result.provider,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=0,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        db_path=db_path,
    )
    return result.vectors[0]


def check_similarity(
    vector: list[float],
    topic: str,
    top_k: int = 5,
    vector_store: VectorStore | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> DedupResult:
    vector_store = vector_store or _default_vector_store()
    matches = vector_store.query(vector=vector, top_k=top_k, filter={"topic": topic})

    for candidate in sorted(matches, key=lambda m: m.score):
        existing = questions_repo.get(
            candidate.metadata["question_id"],
            candidate.metadata["question_version"],
            db_path=db_path,
        )
        if existing is None or existing.status not in COMPARISON_STATUSES:
            continue

        match = DuplicateMatch(
            question_id=existing.id, question_version=existing.version, score=candidate.score
        )
        if candidate.score <= settings.dedup_hard_threshold:
            return DedupResult(is_duplicate=True, match=match)
        if candidate.score <= settings.dedup_soft_threshold:
            return DedupResult(is_flagged=True, match=match)
        # closest surviving match isn't similar enough -- farther ones won't be either
        return DedupResult()

    return DedupResult()


def record_question_embedding(
    question_id: str,
    question_version: int,
    topic: str,
    vector: list[float],
    vector_store: VectorStore | None = None,
) -> None:
    vector_store = vector_store or _default_vector_store()
    vector_store.add(
        ids=[f"{question_id}_{question_version}"],
        vectors=[vector],
        metadata=[
            {"question_id": question_id, "question_version": question_version, "topic": topic}
        ],
    )
