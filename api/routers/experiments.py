from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db_path, get_embedding_provider_dep, get_llm_provider_dep
from api.schemas import RunExperimentRequest
from core.models import Experiment
from db.repositories import experiments_repo
from embeddings.base import EmbeddingProvider
from llm.base import LLMProvider
from services.experiment import ExperimentError, VariantMetrics, aggregate_results, run_experiment

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("", response_model=Experiment)
def create_experiment(
    body: RunExperimentRequest,
    db_path: Path = Depends(get_db_path),
    provider: LLMProvider = Depends(get_llm_provider_dep),
    embedding_provider: EmbeddingProvider | None = Depends(get_embedding_provider_dep),
):
    try:
        return run_experiment(
            name=body.name,
            hypothesis=body.hypothesis,
            variants=body.variants,
            topic=body.topic,
            difficulty=body.difficulty,
            sample_size=body.sample_size,
            reference_answer=body.reference_answer,
            provider=provider,
            embedding_provider=embedding_provider,
            db_path=db_path,
        )
    except ExperimentError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{experiment_id}", response_model=dict[str, VariantMetrics])
def get_experiment_results(
    experiment_id: str,
    db_path: Path = Depends(get_db_path),
    embedding_provider: EmbeddingProvider | None = Depends(get_embedding_provider_dep),
):
    experiment = experiments_repo.get(experiment_id, db_path=db_path)
    if experiment is None:
        raise HTTPException(404, f"No experiment found for id={experiment_id!r}")
    try:
        return aggregate_results(
            experiment_id, embedding_provider=embedding_provider, db_path=db_path
        )
    except ExperimentError as exc:
        raise HTTPException(422, str(exc)) from exc
