import uuid
from datetime import UTC, datetime
from typing import Any

from core.enums import (
    DocumentStatus,
    ExperimentStatus,
    OperationType,
    OverallVerdict,
    QuestionStatus,
    ReviewDecision,
    Source,
)
from core.models import (
    Document,
    Evaluation,
    Experiment,
    ExperimentRun,
    FillBlankPayload,
    FillBlankQuestion,
    McqOption,
    McqPayload,
    McqQuestion,
    DimensionScore,
    Review,
    TrueFalsePayload,
    TrueFalseQuestion,
)
from metadata.models import MetadataRecord


def _now() -> datetime:
    return datetime.now(UTC)


def _uid() -> str:
    return str(uuid.uuid4())


def make_mcq_question(**overrides: Any) -> McqQuestion:
    payload = overrides.pop("payload", None) or McqPayload(
        options=[
            McqOption(id="a", text="Paris", is_correct=True),
            McqOption(id="b", text="Lyon", is_correct=False),
            McqOption(id="c", text="Nice", is_correct=False),
        ],
        correct_option_id="a",
        explanation="Paris is the capital of France.",
    )
    fields: dict[str, Any] = {
        "id": _uid(),
        "version": 1,
        "status": QuestionStatus.GENERATED,
        "stem": "What is the capital of France?",
        "difficulty": "easy",
        "topic": "geography",
        "tags": ["europe"],
        "source": Source.TOPIC,
        "created_at": _now(),
        "created_by": "system",
        "payload": payload,
    }
    fields.update(overrides)
    return McqQuestion(**fields)


def make_true_false_question(**overrides: Any) -> TrueFalseQuestion:
    payload = overrides.pop("payload", None) or TrueFalsePayload(
        correct_answer=True,
        explanation="Water boils at 100C at sea level.",
    )
    fields: dict[str, Any] = {
        "id": _uid(),
        "version": 1,
        "status": QuestionStatus.GENERATED,
        "stem": "Water boils at 100 degrees Celsius at sea level.",
        "difficulty": "easy",
        "topic": "science",
        "source": Source.TOPIC,
        "created_at": _now(),
        "created_by": "system",
        "payload": payload,
    }
    fields.update(overrides)
    return TrueFalseQuestion(**fields)


def make_fill_blank_question(**overrides: Any) -> FillBlankQuestion:
    payload = overrides.pop("payload", None) or FillBlankPayload(
        accepted_answers=["mitochondria", "the mitochondria"],
        blank_marker="___",
        case_sensitive=False,
    )
    fields: dict[str, Any] = {
        "id": _uid(),
        "version": 1,
        "status": QuestionStatus.GENERATED,
        "stem": "The ___ is the powerhouse of the cell.",
        "difficulty": "easy",
        "topic": "biology",
        "source": Source.TOPIC,
        "created_at": _now(),
        "created_by": "system",
        "payload": payload,
    }
    fields.update(overrides)
    return FillBlankQuestion(**fields)


def make_evaluation(question, **overrides: Any) -> Evaluation:
    fields: dict[str, Any] = {
        "id": _uid(),
        "question_id": question.id,
        "question_version": question.version,
        "rubric_id": "rubric_mcq",
        "rubric_version": "v1",
        "scores": {
            "correctness": DimensionScore(score=4, rationale="Answer key verified."),
            "clarity": DimensionScore(score=3, rationale="Stem is clear."),
        },
        "overall_verdict": OverallVerdict.PASS,
        "reference_answer_used": False,
        "evaluation_metadata_id": _uid(),
        "created_at": _now(),
    }
    fields.update(overrides)
    return Evaluation(**fields)


def make_review(question, **overrides: Any) -> Review:
    fields: dict[str, Any] = {
        "id": _uid(),
        "question_id": question.id,
        "question_version": question.version,
        "reviewer_id": "sme_1",
        "decision": ReviewDecision.APPROVE,
        "created_at": _now(),
    }
    fields.update(overrides)
    return Review(**fields)


def make_document(**overrides: Any) -> Document:
    fields: dict[str, Any] = {
        "id": _uid(),
        "title": "Cell Biology 101",
        "original_filename": "cell_biology.pdf",
        "status": DocumentStatus.INGESTED,
        "chunk_count": 0,
        "topic": "biology",
        "tags": [],
        "created_at": _now(),
    }
    fields.update(overrides)
    return Document(**fields)


def make_experiment(**overrides: Any) -> Experiment:
    fields: dict[str, Any] = {
        "id": _uid(),
        "name": "groq-vs-openai",
        "hypothesis": "Model B produces fewer weak distractors than Model A.",
        "variants": [{"key": "a", "model": "llama3-70b"}, {"key": "b", "model": "gpt-4o"}],
        "status": ExperimentStatus.RUNNING,
        "created_at": _now(),
    }
    fields.update(overrides)
    return Experiment(**fields)


def make_experiment_run(experiment, question, **overrides: Any) -> ExperimentRun:
    fields: dict[str, Any] = {
        "id": _uid(),
        "experiment_id": experiment.id,
        "variant_key": "a",
        "question_id": question.id,
        "question_version": question.version,
        "created_at": _now(),
    }
    fields.update(overrides)
    return ExperimentRun(**fields)


def make_metadata_record(**overrides: Any) -> MetadataRecord:
    fields: dict[str, Any] = {
        "id": _uid(),
        "operation_type": OperationType.GENERATION,
        "provider": "groq",
        "model": "llama3-70b",
        "prompt_version": "mcq_v1",
        "input_tokens": 120,
        "output_tokens": 340,
        "latency_ms": 812.5,
        "cost_usd": 0.0012,
        "rag_usage": None,
        "created_at": _now(),
    }
    fields.update(overrides)
    return MetadataRecord(**fields)
