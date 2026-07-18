import json
import sqlite3
from pathlib import Path

from core.enums import OperationType
from db.connection import DEFAULT_DB_PATH, get_connection
from metadata.models import MetadataRecord


def insert(
    record: MetadataRecord, db_path: Path | str = DEFAULT_DB_PATH
) -> MetadataRecord:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO metadata_logs (
                id, operation_type, provider, model, prompt_version,
                input_tokens, output_tokens, latency_ms, cost_usd, rag_usage, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.operation_type.value,
                record.provider,
                record.model,
                record.prompt_version,
                record.input_tokens,
                record.output_tokens,
                record.latency_ms,
                record.cost_usd,
                json.dumps(record.rag_usage) if record.rag_usage is not None else None,
                record.created_at.isoformat(),
            ),
        )
    return record


def get(
    record_id: str, db_path: Path | str = DEFAULT_DB_PATH
) -> MetadataRecord | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM metadata_logs WHERE id = ?", (record_id,)
        ).fetchone()
    return _row_to_record(row) if row is not None else None


def _row_to_record(row: sqlite3.Row) -> MetadataRecord:
    return MetadataRecord(
        id=row["id"],
        operation_type=OperationType(row["operation_type"]),
        provider=row["provider"],
        model=row["model"],
        prompt_version=row["prompt_version"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        latency_ms=row["latency_ms"],
        cost_usd=row["cost_usd"],
        rag_usage=json.loads(row["rag_usage"]) if row["rag_usage"] is not None else None,
        created_at=row["created_at"],
    )
