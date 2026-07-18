from typing import Any

from pydantic import BaseModel

from core.enums import QuestionType, ReviewDecision
from core.models import ReviewFeedback


class GenerateQuestionRequest(BaseModel):
    type: QuestionType
    topic: str
    difficulty: str
    document_id: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    top_k: int = 5
    created_by: str = "api"


class EvaluateRequest(BaseModel):
    question_id: str
    question_version: int
    reference_answer: str | None = None
    model: str | None = None


class SubmitReviewRequest(BaseModel):
    question_id: str
    question_version: int
    reviewer_id: str
    decision: ReviewDecision
    feedback: ReviewFeedback = ReviewFeedback()
    edited_payload: dict[str, Any] | None = None


class RunExperimentRequest(BaseModel):
    name: str
    hypothesis: str
    variants: list[dict[str, Any]]
    topic: str
    difficulty: str
    sample_size: int = 3
    reference_answer: str | None = None
