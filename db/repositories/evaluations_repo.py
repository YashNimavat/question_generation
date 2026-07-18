import json
import sqlite3
from pathlib import Path

from core.enums import OverallVerdict
from core.models import DimensionScore, Evaluation
from db.connection import DEFAULT_DB_PATH, get_connection


def insert(
    evaluation: Evaluation, db_path: Path | str = DEFAULT_DB_PATH
) -> Evaluation:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO evaluations (
                id, question_id, question_version, rubric_id, rubric_version,
                scores, overall_verdict, reference_answer_used, metadata_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation.id,
                evaluation.question_id,
                evaluation.question_version,
                evaluation.rubric_id,
                evaluation.rubric_version,
                json.dumps(
                    {k: v.model_dump(mode="json") for k, v in evaluation.scores.items()}
                ),
                evaluation.overall_verdict.value,
                int(evaluation.reference_answer_used),
                evaluation.evaluation_metadata_id,
                evaluation.created_at.isoformat(),
            ),
        )
    return evaluation


def list_for_question(
    question_id: str, db_path: Path | str = DEFAULT_DB_PATH
) -> list[Evaluation]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM evaluations WHERE question_id = ? ORDER BY created_at",
            (question_id,),
        ).fetchall()
    return [_row_to_evaluation(row) for row in rows]


def _row_to_evaluation(row: sqlite3.Row) -> Evaluation:
    scores_raw = json.loads(row["scores"])
    return Evaluation(
        id=row["id"],
        question_id=row["question_id"],
        question_version=row["question_version"],
        rubric_id=row["rubric_id"],
        rubric_version=row["rubric_version"],
        scores={k: DimensionScore(**v) for k, v in scores_raw.items()},
        overall_verdict=OverallVerdict(row["overall_verdict"]),
        reference_answer_used=bool(row["reference_answer_used"]),
        evaluation_metadata_id=row["metadata_id"],
        created_at=row["created_at"],
    )
