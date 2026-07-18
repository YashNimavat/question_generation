import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from config.settings import settings
from core.enums import OperationType, OverallVerdict, QuestionStatus, QuestionType
from core.models import (
    DimensionScore,
    Evaluation,
    FillBlankQuestion,
    McqQuestion,
    Question,
    TrueFalseQuestion,
)
from core.rubric import Rubric, compute_overall_verdict, get_rubric
from db.connection import DEFAULT_DB_PATH
from db.repositories import evaluations_repo, questions_repo
from llm.base import LLMProvider, Message
from llm.registry import get_llm_provider
from metadata.logger import log_call

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
MAX_ATTEMPTS = 2

# Judge (system) prompt per question type, keyed by prompt_version -- mirrors
# services/generation.py's per-type prompt registration.
JUDGE_PROMPTS: dict[QuestionType, tuple[str, Path]] = {
    QuestionType.MCQ: ("judge_mcq_v1", PROMPTS_DIR / "judge_mcq_v1.txt"),
    QuestionType.TRUE_FALSE: ("judge_true_false_v1", PROMPTS_DIR / "judge_true_false_v1.txt"),
    QuestionType.FILL_BLANK: ("judge_fill_blank_v1", PROMPTS_DIR / "judge_fill_blank_v1.txt"),
}


class EvaluationError(Exception):
    pass


def evaluate(
    question_id: str,
    question_version: int,
    reference_answer: str | None = None,
    provider: LLMProvider | None = None,
    model: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> Evaluation:
    question = questions_repo.get(question_id, question_version, db_path=db_path)
    if question is None:
        raise EvaluationError(
            f"No question found for id={question_id!r} version={question_version}"
        )

    rubric = get_rubric(question.type)
    prompt_version, prompt_path = JUDGE_PROMPTS[question.type]
    provider = provider or get_llm_provider()
    model = model or settings.default_judge_model

    messages = [
        Message(role="system", content=prompt_path.read_text()),
        Message(role="user", content=_build_judge_prompt(question, reference_answer)),
    ]

    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        result = provider.generate(messages, model=model, response_format="json")
        metadata_record = log_call(
            operation_type=OperationType.EVALUATION,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
            prompt_version=prompt_version,
            db_path=db_path,
        )

        try:
            scores = _parse_judge_response(result.text, rubric)
        except (json.JSONDecodeError, ValidationError, ValueError, KeyError, TypeError) as exc:
            last_error = exc
            messages = [
                *messages,
                Message(role="assistant", content=result.text),
                Message(
                    role="user",
                    content=(
                        "Your previous response was not valid JSON matching the required "
                        f"schema ({exc}). Return ONLY the corrected JSON object, with no "
                        "other text."
                    ),
                ),
            ]
            continue

        verdict = compute_overall_verdict(scores)
        evaluation = Evaluation(
            id=str(uuid.uuid4()),
            question_id=question_id,
            question_version=question_version,
            rubric_id=rubric.id,
            rubric_version=rubric.version,
            scores=scores,
            overall_verdict=verdict,
            reference_answer_used=reference_answer is not None,
            evaluation_metadata_id=metadata_record.id,
            created_at=datetime.now(UTC),
        )
        saved = evaluations_repo.insert(evaluation, db_path=db_path)

        new_status = (
            QuestionStatus.REJECTED
            if verdict == OverallVerdict.FAIL
            else QuestionStatus.PENDING_REVIEW
        )
        questions_repo.update_status(question_id, question_version, new_status, db_path=db_path)
        return saved

    raise EvaluationError(
        f"Failed to get a valid judge response for question_id={question_id!r} "
        f"version={question_version} after {MAX_ATTEMPTS} attempts: {last_error}"
    )


def _build_mcq_judge_body(question: McqQuestion) -> str:
    options_text = "\n".join(
        f"  {opt.id}. {opt.text}"
        + (" [marked correct by generator]" if opt.id == question.payload.correct_option_id else "")
        for opt in question.payload.options
    )
    return (
        f"Stem: {question.stem}\n\n"
        f"Options:\n{options_text}\n\n"
        f"Generator's explanation: {question.payload.explanation}"
    )


def _build_true_false_judge_body(question: TrueFalseQuestion) -> str:
    return (
        f"Statement: {question.stem}\n\n"
        f"Generator's label: {question.payload.correct_answer}\n\n"
        f"Generator's explanation: {question.payload.explanation}"
    )


def _build_fill_blank_judge_body(question: FillBlankQuestion) -> str:
    accepted = ", ".join(question.payload.accepted_answers)
    return (
        f"Stem (blank marked with '{question.payload.blank_marker}'): {question.stem}\n\n"
        f"Generator's accepted answers: {accepted}\n\n"
        f"Case sensitive: {question.payload.case_sensitive}\n\n"
        f"Generator's explanation: {question.payload.explanation}"
    )


_JUDGE_BODY_BUILDERS: dict[QuestionType, Callable[[Question], str]] = {
    QuestionType.MCQ: _build_mcq_judge_body,
    QuestionType.TRUE_FALSE: _build_true_false_judge_body,
    QuestionType.FILL_BLANK: _build_fill_blank_judge_body,
}


def _build_judge_prompt(question: Question, reference_answer: str | None) -> str:
    body = _JUDGE_BODY_BUILDERS[question.type](question)
    reference_block = (
        f"Reference answer (SME-supplied, treat as ground truth): {reference_answer}"
        if reference_answer
        else "No reference answer was supplied; use your own domain knowledge to verify correctness."
    )
    return (
        f"Topic: {question.topic}\n"
        f"Target difficulty: {question.difficulty}\n\n"
        f"{body}\n\n"
        f"{reference_block}\n\n"
        "Score this question against the rubric now."
    )


def _parse_judge_response(text: str, rubric: Rubric) -> dict[str, DimensionScore]:
    data = json.loads(text)
    if set(data.keys()) != rubric.dimension_keys:
        raise ValueError(
            f"Judge response keys {sorted(data.keys())} do not match rubric dimensions "
            f"{sorted(rubric.dimension_keys)}"
        )

    scores: dict[str, DimensionScore] = {}
    for key, value in data.items():
        score = DimensionScore(**value)
        if not (1 <= score.score <= 4):
            raise ValueError(f"Dimension {key!r} score {score.score} out of range 1-4")
        scores[key] = score
    return scores
