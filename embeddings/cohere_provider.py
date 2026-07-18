import time

import cohere

from embeddings.base import EmbeddingResult

# USD per 1M input tokens. Hardcoded per docs/TECH_ARCHITECTURE.md ("each provider knows
# its own pricing"). Verify against https://cohere.com/pricing before relying on these for
# real cost accounting -- rates are not fetched live and drift over time.
PRICING_PER_MILLION_TOKENS: dict[str, float] = {
    "embed-english-v3.0": 0.10,
    "embed-multilingual-v3.0": 0.10,
}

# Cohere's embed endpoint caps a single request at 96 input texts.
MAX_TEXTS_PER_REQUEST = 96


class CohereProvider:
    def __init__(self, api_key: str | None = None, client: cohere.Client | None = None) -> None:
        self._client = client if client is not None else cohere.Client(api_key=api_key)

    def embed(
        self, texts: list[str], model: str, input_type: str = "search_document"
    ) -> EmbeddingResult:
        if model not in PRICING_PER_MILLION_TOKENS:
            raise ValueError(
                f"No pricing configured for Cohere model '{model}' -- add it to "
                "PRICING_PER_MILLION_TOKENS before embedding with it."
            )

        vectors: list[list[float]] = []
        input_tokens = 0
        start = time.perf_counter()
        for batch_start in range(0, len(texts), MAX_TEXTS_PER_REQUEST):
            batch = texts[batch_start : batch_start + MAX_TEXTS_PER_REQUEST]
            response = self._client.embed(
                texts=batch,
                model=model,
                input_type=input_type,
            )
            vectors.extend(response.embeddings)
            billed_units = getattr(response.meta, "billed_units", None) if response.meta else None
            input_tokens += int(billed_units.input_tokens) if billed_units and billed_units.input_tokens else 0
        latency_ms = (time.perf_counter() - start) * 1000

        cost_usd = (input_tokens / 1_000_000) * PRICING_PER_MILLION_TOKENS[model]

        return EmbeddingResult(
            vectors=vectors,
            model=model,
            provider="cohere",
            input_tokens=input_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )
