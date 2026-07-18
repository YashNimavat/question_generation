import json
import sqlite3
from pathlib import Path

from core.enums import DocumentStatus
from core.models import Document
from db.connection import DEFAULT_DB_PATH, get_connection


def insert(document: Document, db_path: Path | str = DEFAULT_DB_PATH) -> Document:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO documents (
                id, title, original_filename, status, chunk_count, topic, tags, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.id,
                document.title,
                document.original_filename,
                document.status.value,
                document.chunk_count,
                document.topic,
                json.dumps(document.tags),
                document.created_at.isoformat(),
            ),
        )
    return document


def get(document_id: str, db_path: Path | str = DEFAULT_DB_PATH) -> Document | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
    return _row_to_document(row) if row is not None else None


def update_status(
    document_id: str,
    status: DocumentStatus,
    chunk_count: int | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        if chunk_count is None:
            conn.execute(
                "UPDATE documents SET status = ? WHERE id = ?",
                (status.value, document_id),
            )
        else:
            conn.execute(
                "UPDATE documents SET status = ?, chunk_count = ? WHERE id = ?",
                (status.value, chunk_count, document_id),
            )


def _row_to_document(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"],
        title=row["title"],
        original_filename=row["original_filename"],
        status=DocumentStatus(row["status"]),
        chunk_count=row["chunk_count"],
        topic=row["topic"],
        tags=json.loads(row["tags"]),
        created_at=row["created_at"],
    )
