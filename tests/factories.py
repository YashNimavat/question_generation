import json
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
from embeddings.base import EmbeddingResult
from llm.base import LLMResult, Message
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
        explanation="Mitochondria generate most of the cell's ATP supply.",
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


def make_judge_scores_json(rubric=None, **overrides: Any) -> str:
    """Build valid judge-response JSON text covering every dimension in `rubric`
    (defaults to the MCQ rubric), overridable per dimension key, e.g.
    make_judge_scores_json(correctness={"score": 2, "rationale": "..."})."""
    from core.rubric import MCQ_RUBRIC_V1

    rubric = rubric or MCQ_RUBRIC_V1
    data = {
        dim.key: {"score": 4, "rationale": f"{dim.name} is solid."}
        for dim in rubric.dimensions
    }
    for key, value in overrides.items():
        data[key] = value
    return json.dumps(data)


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


def make_llm_result(**overrides: Any) -> LLMResult:
    fields: dict[str, Any] = {
        "text": "{}",
        "model": "llama-3.3-70b-versatile",
        "provider": "groq",
        "input_tokens": 100,
        "output_tokens": 200,
        "latency_ms": 500.0,
        "cost_usd": 0.0005,
    }
    fields.update(overrides)
    return LLMResult(**fields)


def make_embedding_result(**overrides: Any) -> EmbeddingResult:
    fields: dict[str, Any] = {
        "vectors": [[0.1, 0.2, 0.3]],
        "model": "embed-english-v3.0",
        "provider": "cohere",
        "input_tokens": 50,
        "latency_ms": 120.0,
        "cost_usd": 0.000005,
    }
    fields.update(overrides)
    return EmbeddingResult(**fields)


class FakeEmbeddingProvider:
    """Test double for embeddings.base.EmbeddingProvider. Returns queued results in
    order, recording every call it received for assertions."""

    def __init__(self, results: list[EmbeddingResult]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    def embed(
        self, texts: list[str], model: str, input_type: str = "search_document"
    ) -> EmbeddingResult:
        self.calls.append({"texts": texts, "model": model, "input_type": input_type})
        if not self._results:
            raise AssertionError("FakeEmbeddingProvider.embed called more times than queued results")
        return self._results.pop(0)


class FakeVectorStore:
    """Test double for rag.vector_store.VectorStore. Records add() and query() calls
    and serves query() from whatever has been added, applying `filter` as an exact-match
    on metadata keys (unlike chromadb, no similarity ranking -- add() order is preserved)."""

    def __init__(self) -> None:
        self.added: list[dict[str, Any]] = []
        self.queried: list[dict[str, Any]] = []

    def add(self, ids: list[str], vectors: list[list[float]], metadata: list[dict[str, Any]]) -> None:
        self.added.append({"ids": ids, "vectors": vectors, "metadata": metadata})

    def query(self, vector: list[float], top_k: int, filter: dict[str, Any] | None = None):
        from rag.vector_store import VectorMatch

        self.queried.append({"vector": vector, "top_k": top_k, "filter": filter})

        matches = []
        for batch in self.added:
            for id_, stored_vector, meta in zip(batch["ids"], batch["vectors"], batch["metadata"]):
                if filter and any(meta.get(key) != value for key, value in filter.items()):
                    continue
                matches.append(
                    VectorMatch(id=id_, score=_cosine_distance(vector, stored_vector), metadata=meta)
                )
        matches.sort(key=lambda m: m.score)
        return matches[:top_k]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Mirrors chromadb's cosine distance (1 - cosine similarity) for a collection
    created with hnsw:space=cosine, so fakes exercise dedup thresholds meaningfully."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


class FakeLLMProvider:
    """Test double for llm.base.LLMProvider. Returns queued results in order,
    recording every call it received for assertions."""

    def __init__(self, results: list[LLMResult]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: str = "text",
    ) -> LLMResult:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        if not self._results:
            raise AssertionError("FakeLLMProvider.generate called more times than queued results")
        return self._results.pop(0)
