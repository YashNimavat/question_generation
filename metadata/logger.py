import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.enums import OperationType
from db.connection import DEFAULT_DB_PATH
from db.repositories import metadata_repo
from metadata.models import MetadataRecord


def log_call(
    operation_type: OperationType,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    cost_usd: float,
    prompt_version: str | None = None,
    rag_usage: dict[str, Any] | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> MetadataRecord:
    record = MetadataRecord(
        id=str(uuid.uuid4()),
        operation_type=operation_type,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        rag_usage=rag_usage,
        created_at=datetime.now(UTC),
    )
    return metadata_repo.insert(record, db_path=db_path)
