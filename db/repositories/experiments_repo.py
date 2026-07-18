import json
import sqlite3
from pathlib import Path

from core.enums import ExperimentStatus
from core.models import Experiment, ExperimentRun
from db.connection import DEFAULT_DB_PATH, get_connection


def insert(experiment: Experiment, db_path: Path | str = DEFAULT_DB_PATH) -> Experiment:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO experiments (id, name, hypothesis, variants, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                experiment.id,
                experiment.name,
                experiment.hypothesis,
                json.dumps(experiment.variants),
                experiment.status.value,
                experiment.created_at.isoformat(),
            ),
        )
    return experiment


def get(experiment_id: str, db_path: Path | str = DEFAULT_DB_PATH) -> Experiment | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
        ).fetchone()
    return _row_to_experiment(row) if row is not None else None


def list_all(db_path: Path | str = DEFAULT_DB_PATH) -> list[Experiment]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_experiment(row) for row in rows]


def update_status(
    experiment_id: str, status: ExperimentStatus, db_path: Path | str = DEFAULT_DB_PATH
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE experiments SET status = ? WHERE id = ?",
            (status.value, experiment_id),
        )


def insert_run(
    run: ExperimentRun, db_path: Path | str = DEFAULT_DB_PATH
) -> ExperimentRun:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO experiment_runs (
                id, experiment_id, variant_key, question_id, question_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run.id,
                run.experiment_id,
                run.variant_key,
                run.question_id,
                run.question_version,
                run.created_at.isoformat(),
            ),
        )
    return run


def list_runs(
    experiment_id: str, db_path: Path | str = DEFAULT_DB_PATH
) -> list[ExperimentRun]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_runs WHERE experiment_id = ? ORDER BY created_at",
            (experiment_id,),
        ).fetchall()
    return [_row_to_run(row) for row in rows]


def _row_to_experiment(row: sqlite3.Row) -> Experiment:
    return Experiment(
        id=row["id"],
        name=row["name"],
        hypothesis=row["hypothesis"],
        variants=json.loads(row["variants"]),
        status=ExperimentStatus(row["status"]),
        created_at=row["created_at"],
    )


def _row_to_run(row: sqlite3.Row) -> ExperimentRun:
    return ExperimentRun(
        id=row["id"],
        experiment_id=row["experiment_id"],
        variant_key=row["variant_key"],
        question_id=row["question_id"],
        question_version=row["question_version"],
        created_at=row["created_at"],
    )
