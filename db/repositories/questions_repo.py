import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from core.enums import QuestionStatus, QuestionType, Source
from core.models import QUESTION_TYPE_MODELS, Question
from db.connection import DEFAULT_DB_PATH, get_connection


def insert(question: Question, db_path: Path | str = DEFAULT_DB_PATH) -> Question:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO questions (
                id, version, type, status, stem, payload, difficulty, topic, tags,
                source, document_id, parent_id, parent_version, generation_metadata_id,
                duplicate_of_id, duplicate_of_version, duplicate_score,
                created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question.id,
                question.version,
                question.type.value,
                question.status.value,
                question.stem,
                json.dumps(question.payload.model_dump(mode="json")),
                question.difficulty,
                question.topic,
                json.dumps(question.tags),
                question.source.value,
                question.document_id,
                question.parent_id,
                question.parent_version,
                question.generation_metadata_id,
                question.duplicate_of_id,
                question.duplicate_of_version,
                question.duplicate_score,
                question.created_by,
                question.created_at.isoformat(),
            ),
        )
    return question


def get(
    question_id: str, version: int, db_path: Path | str = DEFAULT_DB_PATH
) -> Question | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM questions WHERE id = ? AND version = ?",
            (question_id, version),
        ).fetchone()
    return _row_to_question(row) if row is not None else None


def get_latest(
    question_id: str, db_path: Path | str = DEFAULT_DB_PATH
) -> Question | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM questions WHERE id = ? ORDER BY version DESC LIMIT 1",
            (question_id,),
        ).fetchone()
    return _row_to_question(row) if row is not None else None


def list_questions(
    topic: str | None = None,
    status: QuestionStatus | None = None,
    type: QuestionType | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[Question]:
    clauses = []
    params: list[str] = []
    if topic is not None:
        clauses.append("topic = ?")
        params.append(topic)
    if status is not None:
        clauses.append("status = ?")
        params.append(status.value)
    if type is not None:
        clauses.append("type = ?")
        params.append(type.value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM questions {where} ORDER BY topic, id, version", params
        ).fetchall()
    return [_row_to_question(row) for row in rows]


def update_status(
    question_id: str,
    version: int,
    status: QuestionStatus,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE questions SET status = ? WHERE id = ? AND version = ?",
            (status.value, question_id, version),
        )


def insert_new_version(
    base: Question,
    payload,
    created_by: str,
    parent_id: str,
    parent_version: int,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> Question:
    model_cls = type(base)
    new_question = model_cls(
        id=base.id,
        version=base.version + 1,
        status=QuestionStatus.GENERATED,
        stem=base.stem,
        difficulty=base.difficulty,
        topic=base.topic,
        tags=base.tags,
        source=base.source,
        document_id=base.document_id,
        generation_metadata_id=None,
        parent_id=parent_id,
        parent_version=parent_version,
        created_at=datetime.now(UTC),
        created_by=created_by,
        payload=payload,
    )
    return insert(new_question, db_path=db_path)


def _row_to_question(row: sqlite3.Row) -> Question:
    question_type = QuestionType(row["type"])
    model_cls = QUESTION_TYPE_MODELS[question_type]
    return model_cls(
        id=row["id"],
        version=row["version"],
        type=question_type,
        status=QuestionStatus(row["status"]),
        stem=row["stem"],
        payload=json.loads(row["payload"]),
        difficulty=row["difficulty"],
        topic=row["topic"],
        tags=json.loads(row["tags"]),
        source=Source(row["source"]),
        document_id=row["document_id"],
        generation_metadata_id=row["generation_metadata_id"],
        parent_id=row["parent_id"],
        parent_version=row["parent_version"],
        duplicate_of_id=row["duplicate_of_id"],
        duplicate_of_version=row["duplicate_of_version"],
        duplicate_score=row["duplicate_score"],
        created_at=row["created_at"],
        created_by=row["created_by"],
    )
