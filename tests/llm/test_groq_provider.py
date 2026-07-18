import pytest

from llm.base import Message
from llm.groq_provider import GroqProvider


class _FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeChoiceMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeChoiceMessage(content)


class _FakeChatCompletionResponse:
    def __init__(self, content: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        self.choices = [_FakeChoice(content)]
        self.model = model
        self.usage = _FakeUsage(prompt_tokens, completion_tokens)


class _FakeCompletions:
    def __init__(self, response: _FakeChatCompletionResponse) -> None:
        self.response = response
        self.received_kwargs: dict = {}

    def create(self, **kwargs):
        self.received_kwargs = kwargs
        return self.response


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeGroqClient:
    def __init__(self, response: _FakeChatCompletionResponse) -> None:
        self.completions = _FakeCompletions(response)
        self.chat = _FakeChat(self.completions)


def test_generate_returns_llm_result_with_computed_cost():
    response = _FakeChatCompletionResponse(
        content='{"stem": "..."}',
        model="llama-3.3-70b-versatile",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
    )
    client = _FakeGroqClient(response)
    provider = GroqProvider(client=client)

    result = provider.generate(
        messages=[Message(role="user", content="hello")],
        model="llama-3.3-70b-versatile",
    )

    assert result.text == '{"stem": "..."}'
    assert result.model == "llama-3.3-70b-versatile"
    assert result.provider == "groq"
    assert result.input_tokens == 1_000_000
    assert result.output_tokens == 1_000_000
    assert result.cost_usd == pytest.approx(0.59 + 0.79)
    assert result.latency_ms >= 0


def test_generate_maps_json_response_format_to_groq_json_object():
    response = _FakeChatCompletionResponse(
        content="{}", model="llama-3.3-70b-versatile", prompt_tokens=1, completion_tokens=1
    )
    client = _FakeGroqClient(response)
    provider = GroqProvider(client=client)

    provider.generate(
        messages=[Message(role="user", content="hello")],
        model="llama-3.3-70b-versatile",
        response_format="json",
    )

    assert client.completions.received_kwargs["response_format"] == {"type": "json_object"}


def test_generate_unknown_model_raises_before_calling_client():
    client = _FakeGroqClient(
        _FakeChatCompletionResponse(content="{}", model="x", prompt_tokens=0, completion_tokens=0)
    )
    provider = GroqProvider(client=client)

    with pytest.raises(ValueError, match="No pricing configured"):
        provider.generate(messages=[Message(role="user", content="hi")], model="unknown-model")

    assert client.completions.received_kwargs == {}
