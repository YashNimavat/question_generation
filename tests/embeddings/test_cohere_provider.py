import pytest

from embeddings.cohere_provider import CohereProvider


class _FakeBilledUnits:
    def __init__(self, input_tokens: float) -> None:
        self.input_tokens = input_tokens


class _FakeMeta:
    def __init__(self, input_tokens: float) -> None:
        self.billed_units = _FakeBilledUnits(input_tokens)


class _FakeEmbedResponse:
    def __init__(self, embeddings: list[list[float]], input_tokens: float) -> None:
        self.embeddings = embeddings
        self.meta = _FakeMeta(input_tokens)


class _FakeCohereClient:
    def __init__(self, responses: list[_FakeEmbedResponse]) -> None:
        self._responses = list(responses)
        self.received_kwargs: list[dict] = []

    def embed(self, **kwargs):
        self.received_kwargs.append(kwargs)
        return self._responses.pop(0)


def test_embed_returns_result_with_computed_cost():
    response = _FakeEmbedResponse(embeddings=[[0.1, 0.2], [0.3, 0.4]], input_tokens=1_000_000)
    client = _FakeCohereClient([response])
    provider = CohereProvider(client=client)

    result = provider.embed(texts=["a", "b"], model="embed-english-v3.0")

    assert result.vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert result.model == "embed-english-v3.0"
    assert result.provider == "cohere"
    assert result.input_tokens == 1_000_000
    assert result.cost_usd == pytest.approx(0.10)
    assert result.latency_ms >= 0
    assert client.received_kwargs[0]["input_type"] == "search_document"


def test_embed_passes_explicit_input_type_for_query_side_embedding():
    response = _FakeEmbedResponse(embeddings=[[0.1, 0.2]], input_tokens=100)
    client = _FakeCohereClient([response])
    provider = CohereProvider(client=client)

    provider.embed(texts=["what is alpha"], model="embed-english-v3.0", input_type="search_query")

    assert client.received_kwargs[0]["input_type"] == "search_query"


def test_embed_batches_requests_over_the_96_text_limit():
    texts = [f"text {i}" for i in range(150)]
    response_1 = _FakeEmbedResponse(embeddings=[[0.0]] * 96, input_tokens=96)
    response_2 = _FakeEmbedResponse(embeddings=[[0.0]] * 54, input_tokens=54)
    client = _FakeCohereClient([response_1, response_2])
    provider = CohereProvider(client=client)

    result = provider.embed(texts=texts, model="embed-english-v3.0")

    assert len(result.vectors) == 150
    assert result.input_tokens == 150
    assert len(client.received_kwargs) == 2
    assert len(client.received_kwargs[0]["texts"]) == 96
    assert len(client.received_kwargs[1]["texts"]) == 54


def test_embed_unknown_model_raises_before_calling_client():
    client = _FakeCohereClient([])
    provider = CohereProvider(client=client)

    with pytest.raises(ValueError, match="No pricing configured"):
        provider.embed(texts=["a"], model="unknown-model")

    assert client.received_kwargs == []
