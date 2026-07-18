from pathlib import Path
from typing import Any, Protocol

import chromadb
from pydantic import BaseModel

COLLECTION_NAME = "chunks"


class VectorMatch(BaseModel):
    id: str
    score: float
    metadata: dict[str, Any]


class VectorStore(Protocol):
    def add(self, ids: list[str], vectors: list[list[float]], metadata: list[dict[str, Any]]) -> None: ...

    def query(
        self, vector: list[float], top_k: int, filter: dict[str, Any] | None = None
    ) -> list[VectorMatch]: ...


class ChromaVectorStore:
    def __init__(
        self,
        persist_dir: Path | str,
        collection_name: str = COLLECTION_NAME,
        metadata: dict[str, Any] | None = None,
        client: Any | None = None,
    ) -> None:
        self._client = client if client is not None else chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(collection_name, metadata=metadata)

    def add(self, ids: list[str], vectors: list[list[float]], metadata: list[dict[str, Any]]) -> None:
        self._collection.add(ids=ids, embeddings=vectors, metadatas=metadata)

    def query(
        self, vector: list[float], top_k: int, filter: dict[str, Any] | None = None
    ) -> list[VectorMatch]:
        results = self._collection.query(
            query_embeddings=[vector], n_results=top_k, where=filter
        )
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]
        return [
            VectorMatch(id=id_, score=distance, metadata=meta)
            for id_, distance, meta in zip(ids, distances, metadatas)
        ]
