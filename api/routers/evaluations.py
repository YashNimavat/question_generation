from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db_path, get_llm_provider_dep
from api.schemas import EvaluateRequest
from core.models import Evaluation
from db.repositories import evaluations_repo, questions_repo
from llm.base import LLMProvider
from services.evaluation import EvaluationError, evaluate

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("", response_model=Evaluation)
def create_evaluation(
    body: EvaluateRequest,
    db_path: Path = Depends(get_db_path),
    provider: LLMProvider = Depends(get_llm_provider_dep),
):
    question = questions_repo.get(body.question_id, body.question_version, db_path=db_path)
    if question is None:
        raise HTTPException(
            404, f"No question found for id={body.question_id!r} version={body.question_version}"
        )
    try:
        return evaluate(
            question_id=body.question_id,
            question_version=body.question_version,
            reference_answer=body.reference_answer,
            provider=provider,
            model=body.model,
            db_path=db_path,
        )
    except EvaluationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{question_id}", response_model=list[Evaluation])
def list_evaluations(question_id: str, db_path: Path = Depends(get_db_path)):
    return evaluations_repo.list_for_question(question_id, db_path=db_path)
