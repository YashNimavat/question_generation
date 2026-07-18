from pathlib import Path

from pydantic import BaseModel

from config.settings import settings
from core.enums import OperationType
from db.connection import DEFAULT_DB_PATH
from embeddings.base import EmbeddingProvider
from embeddings.registry import get_embedding_provider
from metadata.logger import log_call
from rag.vector_store import ChromaVectorStore, VectorStore


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    score: float


def get_relevant_chunks(
    query: str,
    document_id: str,
    top_k: int = 5,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str | None = None,
    vector_store: VectorStore | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[RetrievedChunk]:
    embedding_provider = embedding_provider or get_embedding_provider()
    embedding_model = embedding_model or settings.default_embedding_model
    vector_store = vector_store or ChromaVectorStore(persist_dir=settings.chroma_persist_dir)

    result = embedding_provider.embed(
        [query], model=embedding_model, input_type="search_query"
    )
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
    matches = vector_store.query(
        vector=result.vectors[0], top_k=top_k, filter={"document_id": document_id}
    )

    return [
        RetrievedChunk(
            chunk_id=match.id,
            document_id=match.metadata["document_id"],
            chunk_index=match.metadata["chunk_index"],
            text=match.metadata["text"],
            score=match.score,
        )
        for match in matches
    ]
