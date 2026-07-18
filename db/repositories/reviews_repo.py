import sqlite3
from pathlib import Path

from core.enums import ReasonCategory, ReviewDecision, Severity
from core.models import Review
from db.connection import DEFAULT_DB_PATH, get_connection


def insert(review: Review, db_path: Path | str = DEFAULT_DB_PATH) -> Review:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO reviews (
                id, question_id, question_version, reviewer_id, decision,
                reason_category, comment, severity, linked_new_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review.id,
                review.question_id,
                review.question_version,
                review.reviewer_id,
                review.decision.value,
                review.reason_category.value if review.reason_category else None,
                review.comment,
                review.severity.value if review.severity else None,
                review.linked_new_version,
                review.created_at.isoformat(),
            ),
        )
    return review


def list_for_question(
    question_id: str, db_path: Path | str = DEFAULT_DB_PATH
) -> list[Review]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE question_id = ? ORDER BY created_at",
            (question_id,),
        ).fetchall()
    return [_row_to_review(row) for row in rows]


def _row_to_review(row: sqlite3.Row) -> Review:
    return Review(
        id=row["id"],
        question_id=row["question_id"],
        question_version=row["question_version"],
        reviewer_id=row["reviewer_id"],
        decision=ReviewDecision(row["decision"]),
        reason_category=ReasonCategory(row["reason_category"])
        if row["reason_category"]
        else None,
        comment=row["comment"],
        severity=Severity(row["severity"]) if row["severity"] else None,
        linked_new_version=row["linked_new_version"],
        created_at=row["created_at"],
    )
