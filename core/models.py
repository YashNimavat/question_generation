from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, model_validator

from core.enums import (
    DocumentStatus,
    ExperimentStatus,
    OverallVerdict,
    QuestionStatus,
    QuestionType,
    ReasonCategory,
    ReviewDecision,
    Severity,
    Source,
)

# ---------------------------------------------------------------------------
# Type-specific payloads
# ---------------------------------------------------------------------------


class McqOption(BaseModel):
    id: str
    text: str
    is_correct: bool


class McqPayload(BaseModel):
    options: list[McqOption]
    correct_option_id: str
    explanation: str

    @model_validator(mode="after")
    def _exactly_one_correct_option(self) -> "McqPayload":
        correct_ids = [o.id for o in self.options if o.is_correct]
        if len(correct_ids) != 1:
            raise ValueError(
                f"MCQ payload must have exactly one correct option, found {len(correct_ids)}"
            )
        if correct_ids[0] != self.correct_option_id:
            raise ValueError(
                "correct_option_id must match the option flagged is_correct=True"
            )
        return self


class TrueFalsePayload(BaseModel):
    correct_answer: bool
    explanation: str


class FillBlankPayload(BaseModel):
    accepted_answers: list[str]
    blank_marker: str
    explanation: str
    case_sensitive: bool = False


# ---------------------------------------------------------------------------
# Question — type-discriminated model
# ---------------------------------------------------------------------------


class QuestionBase(BaseModel):
    id: str
    version: int = 1
    status: QuestionStatus = QuestionStatus.GENERATED
    stem: str
    difficulty: str
    topic: str
    tags: list[str] = Field(default_factory=list)
    source: Source
    document_id: str | None = None
    generation_metadata_id: str | None = None
    parent_id: str | None = None
    parent_version: int | None = None
    duplicate_of_id: str | None = None
    duplicate_of_version: int | None = None
    duplicate_score: float | None = None
    created_at: datetime
    created_by: str


class McqQuestion(QuestionBase):
    type: Literal[QuestionType.MCQ] = QuestionType.MCQ
    payload: McqPayload


class TrueFalseQuestion(QuestionBase):
    type: Literal[QuestionType.TRUE_FALSE] = QuestionType.TRUE_FALSE
    payload: TrueFalsePayload


class FillBlankQuestion(QuestionBase):
    type: Literal[QuestionType.FILL_BLANK] = QuestionType.FILL_BLANK
    payload: FillBlankPayload


Question = Annotated[
    Union[McqQuestion, TrueFalseQuestion, FillBlankQuestion],
    Field(discriminator="type"),
]

QUESTION_TYPE_MODELS: dict[QuestionType, type[BaseModel]] = {
    QuestionType.MCQ: McqQuestion,
    QuestionType.TRUE_FALSE: TrueFalseQuestion,
    QuestionType.FILL_BLANK: FillBlankQuestion,
}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class DimensionScore(BaseModel):
    score: int
    rationale: str


class Evaluation(BaseModel):
    id: str
    question_id: str
    question_version: int
    rubric_id: str
    rubric_version: str
    scores: dict[str, DimensionScore]
    overall_verdict: OverallVerdict
    reference_answer_used: bool = False
    evaluation_metadata_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Review (SME feedback)
# ---------------------------------------------------------------------------


class ReviewFeedback(BaseModel):
    reason_category: ReasonCategory | None = None
    comment: str | None = None
    severity: Severity | None = None


class Review(BaseModel):
    id: str
    question_id: str
    question_version: int
    reviewer_id: str
    decision: ReviewDecision
    reason_category: ReasonCategory | None = None
    comment: str | None = None
    severity: Severity | None = None
    linked_new_version: int | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _reason_required_unless_approved(self) -> "Review":
        if self.decision != ReviewDecision.APPROVE and self.reason_category is None:
            raise ValueError("reason_category is required unless decision is 'approve'")
        return self

    @model_validator(mode="after")
    def _linked_version_only_on_edit(self) -> "Review":
        if self.decision == ReviewDecision.EDIT and self.linked_new_version is None:
            raise ValueError("linked_new_version is required when decision is 'edit'")
        if self.decision != ReviewDecision.EDIT and self.linked_new_version is not None:
            raise ValueError("linked_new_version may only be set when decision is 'edit'")
        return self


# ---------------------------------------------------------------------------
# Document (RAG source)
# ---------------------------------------------------------------------------


class Document(BaseModel):
    id: str
    title: str
    original_filename: str
    status: DocumentStatus = DocumentStatus.INGESTED
    chunk_count: int = 0
    topic: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------


class Experiment(BaseModel):
    id: str
    name: str
    hypothesis: str
    variants: list[dict[str, Any]]
    status: ExperimentStatus = ExperimentStatus.RUNNING
    created_at: datetime


class ExperimentRun(BaseModel):
    id: str
    experiment_id: str
    variant_key: str
    question_id: str
    question_version: int
    created_at: datetime
