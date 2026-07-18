from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db_path, get_embedding_provider_dep, get_llm_provider_dep
from api.schemas import GenerateQuestionRequest
from core.enums import QuestionStatus, QuestionType
from core.models import Question
from db.repositories import questions_repo
from embeddings.base import EmbeddingProvider
from llm.base import LLMProvider
from services.generation import (
    GenerationError,
    generate_fill_blank,
    generate_mcq,
    generate_true_false,
)

router = APIRouter(prefix="/questions", tags=["questions"])

_GENERATORS = {
    QuestionType.MCQ: generate_mcq,
    QuestionType.TRUE_FALSE: generate_true_false,
    QuestionType.FILL_BLANK: generate_fill_blank,
}


@router.post("/generate", response_model=Question)
def generate_question(
    body: GenerateQuestionRequest,
    db_path: Path = Depends(get_db_path),
    provider: LLMProvider = Depends(get_llm_provider_dep),
    embedding_provider: EmbeddingProvider | None = Depends(get_embedding_provider_dep),
):
    if body.prompt_version is not None and body.type != QuestionType.MCQ:
        raise HTTPException(422, "prompt_version is only supported for type='mcq'")

    generator = _GENERATORS[body.type]
    kwargs = dict(
        topic=body.topic,
        difficulty=body.difficulty,
        document_id=body.document_id,
        provider=provider,
        model=body.model,
        top_k=body.top_k,
        embedding_provider=embedding_provider,
        created_by=body.created_by,
        db_path=db_path,
    )
    if body.type == QuestionType.MCQ:
        kwargs["prompt_version"] = body.prompt_version

    try:
        return generator(**kwargs)
    except GenerationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("", response_model=list[Question])
def list_questions(
    topic: str | None = None,
    status: QuestionStatus | None = None,
    type: QuestionType | None = None,
    db_path: Path = Depends(get_db_path),
):
    return questions_repo.list_questions(topic=topic, status=status, type=type, db_path=db_path)


@router.get("/{question_id}", response_model=Question)
def get_question(
    question_id: str,
    version: int | None = None,
    db_path: Path = Depends(get_db_path),
):
    question = (
        questions_repo.get(question_id, version, db_path=db_path)
        if version is not None
        else questions_repo.get_latest(question_id, db_path=db_path)
    )
    if question is None:
        raise HTTPException(404, f"No question found for id={question_id!r}")
    return question
