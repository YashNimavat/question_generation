from typing import Protocol

from pydantic import BaseModel


class EmbeddingResult(BaseModel):
    vectors: list[list[float]]
    model: str
    provider: str
    input_tokens: int
    latency_ms: float
    cost_usd: float


class EmbeddingProvider(Protocol):
    def embed(
        self, texts: list[str], model: str, input_type: str = "search_document"
    ) -> EmbeddingResult: ...
