import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from config.settings import settings
from core.enums import ExperimentStatus, OverallVerdict, QuestionStatus
from core.models import Experiment, ExperimentRun
from db.connection import DEFAULT_DB_PATH
from db.repositories import evaluations_repo, experiments_repo, metadata_repo, questions_repo
from embeddings.base import EmbeddingProvider
from llm.base import LLMProvider
from rag.vector_store import VectorStore
from services import dedup
from services.evaluation import EvaluationError, evaluate
from services.generation import GenerationError, generate_mcq

# The single-axis-per-experiment rule (SYSTEM_DESIGN.md SS7.1): comparing more than
# one of these at once conflates variables and produces an uninterpretable result.
VARIANT_AXES = ("model", "prompt_version", "document_id")


class ExperimentError(Exception):
    pass


class VariantMetrics(BaseModel):
    run_count: int
    evaluated_count: int
    pass_rate: float | None = None
    avg_scores: dict[str, float] = {}
    near_duplicate_rate: float | None = None
    avg_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    avg_generation_latency_ms: float | None = None
    avg_evaluation_latency_ms: float | None = None


def _validate_variants(variants: list[dict[str, Any]]) -> None:
    if len(variants) < 2:
        raise ExperimentError("An experiment needs at least two variants to compare.")

    keys = [v.get("key") for v in variants]
    if any(k is None for k in keys):
        raise ExperimentError("Every variant must have a 'key'.")
    if len(set(keys)) != len(keys):
        raise ExperimentError(f"Variant keys must be unique, got {keys!r}.")

    varying_axes = [
        axis for axis in VARIANT_AXES if len({v.get(axis) for v in variants}) > 1
    ]
    if len(varying_axes) > 1:
        raise ExperimentError(
            "Only one axis may vary per experiment (SYSTEM_DESIGN.md SS7.1), but "
            f"these differ across variants: {varying_axes!r}. Split into separate "
            "experiments, one per axis."
        )


def run_experiment(
    name: str,
    hypothesis: str,
    variants: list[dict[str, Any]],
    topic: str,
    difficulty: str,
    sample_size: int = 3,
    reference_answer: str | None = None,
    provider: LLMProvider | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: VectorStore | None = None,
    dedup_vector_store: VectorStore | None = None,
    created_by: str = "system",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> Experiment:
    _validate_variants(variants)

    experiment = Experiment(
        id=str(uuid.uuid4()),
        name=name,
        hypothesis=hypothesis,
        variants=variants,
        status=ExperimentStatus.RUNNING,
        created_at=datetime.now(UTC),
    )
    experiments_repo.insert(experiment, db_path=db_path)

    for variant in variants:
        variant_key = variant["key"]
        for _ in range(sample_size):
            try:
                question = generate_mcq(
                    topic=topic,
                    difficulty=difficulty,
                    document_id=variant.get("document_id"),
                    prompt_version=variant.get("prompt_version"),
                    model=variant.get("model"),
                    provider=provider,
                    embedding_provider=embedding_provider,
                    vector_store=vector_store,
                    dedup_vector_store=dedup_vector_store,
                    created_by=created_by,
                    db_path=db_path,
                )
            except GenerationError:
                # One bad sample shouldn't abort the whole comparison -- a lower
                # run_count for this variant is itself a visible signal, not
                # something to hide (docs/DECISIONS.md, Slice 9).
                continue

            experiments_repo.insert_run(
                ExperimentRun(
                    id=str(uuid.uuid4()),
                    experiment_id=experiment.id,
                    variant_key=variant_key,
                    question_id=question.id,
                    question_version=question.version,
                    created_at=datetime.now(UTC),
                ),
                db_path=db_path,
            )

            if question.status == QuestionStatus.REJECTED and question.duplicate_of_id is not None:
                # Hard-rejected duplicate -- nothing meaningful left to judge.
                continue

            try:
                evaluate(
                    question_id=question.id,
                    question_version=question.version,
                    reference_answer=reference_answer,
                    provider=provider,
                    db_path=db_path,
                )
            except EvaluationError:
                continue

    experiments_repo.update_status(experiment.id, ExperimentStatus.COMPLETE, db_path=db_path)
    return experiments_repo.get(experiment.id, db_path=db_path)


def aggregate_results(
    experiment_id: str,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict[str, VariantMetrics]:
    experiment = experiments_repo.get(experiment_id, db_path=db_path)
    if experiment is None:
        raise ExperimentError(f"No experiment found for id={experiment_id!r}")

    runs = experiments_repo.list_runs(experiment_id, db_path=db_path)
    runs_by_variant: dict[str, list[ExperimentRun]] = {}
    for run in runs:
        runs_by_variant.setdefault(run.variant_key, []).append(run)

    results: dict[str, VariantMetrics] = {}
    for variant in experiment.variants:
        variant_key = variant["key"]
        variant_runs = runs_by_variant.get(variant_key, [])
        results[variant_key] = _aggregate_variant(
            variant_runs,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            db_path=db_path,
        )
    return results


def _aggregate_variant(
    runs: list[ExperimentRun],
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> VariantMetrics:
    run_count = len(runs)
    if run_count == 0:
        return VariantMetrics(run_count=0, evaluated_count=0)

    questions = [
        questions_repo.get(run.question_id, run.question_version, db_path=db_path)
        for run in runs
    ]
    questions = [q for q in questions if q is not None]

    generation_costs: list[float] = []
    generation_latencies: list[float] = []
    for question in questions:
        if question.generation_metadata_id is None:
            continue
        record = metadata_repo.get(question.generation_metadata_id, db_path=db_path)
        if record is not None:
            generation_costs.append(record.cost_usd)
            generation_latencies.append(record.latency_ms)

    evaluations = []
    for question in questions:
        for evaluation in evaluations_repo.list_for_question(question.id, db_path=db_path):
            if evaluation.question_version == question.version:
                evaluations.append(evaluation)

    evaluation_costs: list[float] = []
    evaluation_latencies: list[float] = []
    for evaluation in evaluations:
        record = metadata_repo.get(evaluation.evaluation_metadata_id, db_path=db_path)
        if record is not None:
            evaluation_costs.append(record.cost_usd)
            evaluation_latencies.append(record.latency_ms)

    pass_rate = None
    avg_scores: dict[str, float] = {}
    if evaluations:
        pass_rate = sum(1 for e in evaluations if e.overall_verdict == OverallVerdict.PASS) / len(
            evaluations
        )
        dimension_totals: dict[str, list[int]] = {}
        for evaluation in evaluations:
            for key, dim_score in evaluation.scores.items():
                dimension_totals.setdefault(key, []).append(dim_score.score)
        avg_scores = {key: sum(vals) / len(vals) for key, vals in dimension_totals.items()}

    near_duplicate_rate = dedup.batch_near_duplicate_rate(
        [q.stem for q in questions],
        threshold=settings.dedup_soft_threshold,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        db_path=db_path,
    )

    total_cost = sum(generation_costs) + sum(evaluation_costs)

    return VariantMetrics(
        run_count=run_count,
        evaluated_count=len(evaluations),
        pass_rate=pass_rate,
        avg_scores=avg_scores,
        near_duplicate_rate=near_duplicate_rate,
        avg_cost_usd=total_cost / run_count if run_count else 0.0,
        total_cost_usd=total_cost,
        avg_generation_latency_ms=(
            sum(generation_latencies) / len(generation_latencies) if generation_latencies else None
        ),
        avg_evaluation_latency_ms=(
            sum(evaluation_latencies) / len(evaluation_latencies) if evaluation_latencies else None
        ),
    )
