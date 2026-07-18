from typing import Literal, Protocol

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMResult(BaseModel):
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    raw_response: dict | None = None


class LLMProvider(Protocol):
    def generate(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResult: ...
