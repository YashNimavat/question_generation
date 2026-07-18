from pathlib import Path

from db.connection import DEFAULT_DB_PATH
from embeddings.base import EmbeddingProvider
from embeddings.registry import get_embedding_provider
from llm.base import LLMProvider
from llm.registry import get_llm_provider
from rag.vector_store import VectorStore


def get_db_path() -> Path | str:
    return DEFAULT_DB_PATH


def get_llm_provider_dep() -> LLMProvider:
    return get_llm_provider()


def get_embedding_provider_dep() -> EmbeddingProvider | None:
    # Cohere is optional (config/settings.py, embeddings/registry.py) -- services
    # that need embeddings already fall back to get_embedding_provider() themselves
    # and turn a missing key into a proper service-level error; routes that don't
    # strictly need embeddings (e.g. topic-only generation's dedup check) degrade
    # gracefully on None, matching services/dedup.py's existing behavior.
    try:
        return get_embedding_provider()
    except ValueError:
        return None


def get_vector_store_dep() -> VectorStore | None:
    # None -> services construct their own ChromaVectorStore(settings.chroma_persist_dir)
    # by default; this dependency exists purely so tests can override it with an
    # in-memory FakeVectorStore instead of touching disk.
    return None
