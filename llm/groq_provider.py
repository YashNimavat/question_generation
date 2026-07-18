import time
from typing import Literal

from groq import Groq

from llm.base import LLMResult, Message

# USD per 1M tokens, as (input_rate, output_rate). Hardcoded per docs/TECH_ARCHITECTURE.md
# ("each provider knows its own pricing"). Verify against https://groq.com/pricing before
# relying on these for real cost accounting -- rates are not fetched live and drift over time.
PRICING_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
}


class GroqProvider:
    def __init__(self, api_key: str | None = None, client: Groq | None = None) -> None:
        self._client = client if client is not None else Groq(api_key=api_key)

    def generate(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResult:
        if model not in PRICING_PER_MILLION_TOKENS:
            raise ValueError(
                f"No pricing configured for Groq model '{model}' -- add it to "
                "PRICING_PER_MILLION_TOKENS before generating with it."
            )

        kwargs: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        response = self._client.chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - start) * 1000

        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        input_rate, output_rate = PRICING_PER_MILLION_TOKENS[model]
        cost_usd = (input_tokens / 1_000_000) * input_rate + (
            output_tokens / 1_000_000
        ) * output_rate

        return LLMResult(
            text=response.choices[0].message.content,
            model=response.model,
            provider="groq",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )
