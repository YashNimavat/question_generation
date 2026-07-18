from datetime import datetime
from typing import Any

from pydantic import BaseModel

from core.enums import OperationType


class MetadataRecord(BaseModel):
    id: str
    operation_type: OperationType
    provider: str
    model: str
    prompt_version: str | None = None
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    rag_usage: dict[str, Any] | None = None
    created_at: datetime
