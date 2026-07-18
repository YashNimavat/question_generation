import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from config.settings import settings
from core.enums import OperationType, QuestionStatus, QuestionType, Source
from core.models import (
    FillBlankPayload,
    FillBlankQuestion,
    McqPayload,
    McqQuestion,
    TrueFalsePayload,
    TrueFalseQuestion,
)
from db.connection import DEFAULT_DB_PATH
from db.repositories import questions_repo
from embeddings.base import EmbeddingProvider
from llm.base import LLMProvider, Message
from llm.registry import get_llm_provider
from metadata.logger import log_call
from rag.grounding import build_grounded_context
from rag.retrieval import get_relevant_chunks
from rag.vector_store import VectorStore
from services import dedup

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
MAX_ATTEMPTS = 2

MCQ_PROMPT_VERSION = "mcq_v1"
MCQ_PROMPT_PATH = PROMPTS_DIR / "mcq_v1.txt"
MCQ_GROUNDED_PROMPT_VERSION = "mcq_grounded_v1"
MCQ_GROUNDED_PROMPT_PATH = PROMPTS_DIR / "mcq_grounded_v1.txt"

# Topic-only prompt variants, keyed by prompt_version -- an experimentation axis
# (Slice 9). Only MCQ has more than one prompt version so far; the grounded (RAG)
# pipeline has only one prompt per type and doesn't accept a prompt_version
# override. Referenced directly by app/pages/6_experiments.py.
PROMPT_VERSIONS: dict[str, Path] = {
    MCQ_PROMPT_VERSION: MCQ_PROMPT_PATH,
    "mcq_v2": PROMPTS_DIR / "mcq_v2.txt",
}

TRUE_FALSE_PROMPT_VERSION = "true_false_v1"
TRUE_FALSE_PROMPT_PATH = PROMPTS_DIR / "true_false_v1.txt"
TRUE_FALSE_GROUNDED_PROMPT_VERSION = "true_false_grounded_v1"
TRUE_FALSE_GROUNDED_PROMPT_PATH = PROMPTS_DIR / "true_false_grounded_v1.txt"

FILL_BLANK_PROMPT_VERSION = "fill_blank_v1"
FILL_BLANK_PROMPT_PATH = PROMPTS_DIR / "fill_blank_v1.txt"
FILL_BLANK_GROUNDED_PROMPT_VERSION = "fill_blank_grounded_v1"
FILL_BLANK_GROUNDED_PROMPT_PATH = PROMPTS_DIR / "fill_blank_grounded_v1.txt"


class GenerationError(Exception):
    pass


def generate_mcq(
    topic: str,
    difficulty: str,
    document_id: str | None = None,
    prompt_version: str | None = None,
    provider: LLMProvider | None = None,
    model: str | None = None,
    top_k: int = 5,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str | None = None,
    vector_store: VectorStore | None = None,
    dedup_vector_store: VectorStore | None = None,
    created_by: str = "system",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> McqQuestion:
    return _generate(
        question_type=QuestionType.MCQ,
        model_cls=McqQuestion,
        parse_response=_parse_mcq_response,
        prompt_versions=PROMPT_VERSIONS,
        default_prompt_version=MCQ_PROMPT_VERSION,
        grounded_prompt_version=MCQ_GROUNDED_PROMPT_VERSION,
        grounded_prompt_path=MCQ_GROUNDED_PROMPT_PATH,
        topic_instruction="Generate one multiple-choice question now.",
        grounded_instruction=(
            "Generate one multiple-choice question now, grounded only in the "
            "source material above."
        ),
        topic=topic,
        difficulty=difficulty,
        document_id=document_id,
        prompt_version=prompt_version,
        provider=provider,
        model=model,
        top_k=top_k,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        vector_store=vector_store,
        dedup_vector_store=dedup_vector_store,
        created_by=created_by,
        db_path=db_path,
    )


def generate_true_false(
    topic: str,
    difficulty: str,
    document_id: str | None = None,
    provider: LLMProvider | None = None,
    model: str | None = None,
    top_k: int = 5,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str | None = None,
    vector_store: VectorStore | None = None,
    dedup_vector_store: VectorStore | None = None,
    created_by: str = "system",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> TrueFalseQuestion:
    return _generate(
        question_type=QuestionType.TRUE_FALSE,
        model_cls=TrueFalseQuestion,
        parse_response=_parse_true_false_response,
        prompt_versions={TRUE_FALSE_PROMPT_VERSION: TRUE_FALSE_PROMPT_PATH},
        default_prompt_version=TRUE_FALSE_PROMPT_VERSION,
        grounded_prompt_version=TRUE_FALSE_GROUNDED_PROMPT_VERSION,
        grounded_prompt_path=TRUE_FALSE_GROUNDED_PROMPT_PATH,
        topic_instruction="Generate one True/False statement now.",
        grounded_instruction=(
            "Generate one True/False statement now, grounded only in the "
            "source material above."
        ),
        topic=topic,
        difficulty=difficulty,
        document_id=document_id,
        prompt_version=None,
        provider=provider,
        model=model,
        top_k=top_k,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        vector_store=vector_store,
        dedup_vector_store=dedup_vector_store,
        created_by=created_by,
        db_path=db_path,
    )


def generate_fill_blank(
    topic: str,
    difficulty: str,
    document_id: str | None = None,
    provider: LLMProvider | None = None,
    model: str | None = None,
    top_k: int = 5,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str | None = None,
    vector_store: VectorStore | None = None,
    dedup_vector_store: VectorStore | None = None,
    created_by: str = "system",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> FillBlankQuestion:
    return _generate(
        question_type=QuestionType.FILL_BLANK,
        model_cls=FillBlankQuestion,
        parse_response=_parse_fill_blank_response,
        prompt_versions={FILL_BLANK_PROMPT_VERSION: FILL_BLANK_PROMPT_PATH},
        default_prompt_version=FILL_BLANK_PROMPT_VERSION,
        grounded_prompt_version=FILL_BLANK_GROUNDED_PROMPT_VERSION,
        grounded_prompt_path=FILL_BLANK_GROUNDED_PROMPT_PATH,
        topic_instruction="Generate one Fill-in-the-Blank question now.",
        grounded_instruction=(
            "Generate one Fill-in-the-Blank question now, grounded only in the "
            "source material above."
        ),
        topic=topic,
        difficulty=difficulty,
        document_id=document_id,
        prompt_version=None,
        provider=provider,
        model=model,
        top_k=top_k,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        vector_store=vector_store,
        dedup_vector_store=dedup_vector_store,
        created_by=created_by,
        db_path=db_path,
    )


def _generate(
    *,
    question_type: QuestionType,
    model_cls: type,
    parse_response: Callable[[str], tuple[str, Any]],
    prompt_versions: dict[str, Path],
    default_prompt_version: str,
    grounded_prompt_version: str,
    grounded_prompt_path: Path,
    topic_instruction: str,
    grounded_instruction: str,
    topic: str,
    difficulty: str,
    document_id: str | None,
    prompt_version: str | None,
    provider: LLMProvider | None,
    model: str | None,
    top_k: int,
    embedding_provider: EmbeddingProvider | None,
    embedding_model: str | None,
    vector_store: VectorStore | None,
    dedup_vector_store: VectorStore | None,
    created_by: str,
    db_path: Path | str,
):
    provider = provider or get_llm_provider()
    model = model or settings.default_llm_model

    rag_usage: dict | None = None
    if document_id is not None:
        if prompt_version is not None:
            raise GenerationError(
                "prompt_version override is not supported for RAG-grounded generation "
                "(document_id is set) -- the grounded pipeline has only one prompt."
            )
        try:
            chunks = get_relevant_chunks(
                query=topic,
                document_id=document_id,
                top_k=top_k,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                vector_store=vector_store,
                db_path=db_path,
            )
        except ValueError as exc:
            raise GenerationError(f"Embedding provider unavailable: {exc}") from exc
        if not chunks:
            raise GenerationError(
                f"No relevant chunks found for document_id={document_id!r} "
                f"and topic={topic!r} -- cannot ground generation."
            )
        prompt_path = grounded_prompt_path
        prompt_version = grounded_prompt_version
        user_content = (
            f"Topic: {topic}\nDifficulty: {difficulty}\n\n"
            f"Source material:\n{build_grounded_context(chunks)}\n\n"
            f"{grounded_instruction}"
        )
        rag_usage = {"document_id": document_id, "chunk_ids": [c.chunk_id for c in chunks]}
    else:
        prompt_version = prompt_version or default_prompt_version
        try:
            prompt_path = prompt_versions[prompt_version]
        except KeyError:
            raise GenerationError(
                f"Unknown prompt_version={prompt_version!r}; must be one of "
                f"{sorted(prompt_versions)}"
            ) from None
        user_content = f"Topic: {topic}\nDifficulty: {difficulty}\n{topic_instruction}"

    messages = [
        Message(role="system", content=prompt_path.read_text()),
        Message(role="user", content=user_content),
    ]

    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        result = provider.generate(messages, model=model, response_format="json")
        metadata_record = log_call(
            operation_type=OperationType.GENERATION,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
            prompt_version=prompt_version,
            rag_usage=rag_usage,
            db_path=db_path,
        )

        try:
            stem, payload = parse_response(result.text)
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

        dedup_vector = dedup.embed_stem(
            stem, embedding_provider=embedding_provider, embedding_model=embedding_model, db_path=db_path
        )
        dedup_result = (
            dedup.check_similarity(
                dedup_vector, topic=topic, vector_store=dedup_vector_store, db_path=db_path
            )
            if dedup_vector is not None
            else dedup.DedupResult()
        )

        question_id = str(uuid.uuid4())
        question = model_cls(
            id=question_id,
            version=1,
            status=QuestionStatus.REJECTED if dedup_result.is_duplicate else QuestionStatus.GENERATED,
            stem=stem,
            difficulty=difficulty,
            topic=topic,
            source=Source.DOCUMENT if document_id is not None else Source.TOPIC,
            document_id=document_id,
            generation_metadata_id=metadata_record.id,
            duplicate_of_id=dedup_result.match.question_id if dedup_result.match else None,
            duplicate_of_version=dedup_result.match.question_version if dedup_result.match else None,
            duplicate_score=dedup_result.match.score if dedup_result.match else None,
            created_at=datetime.now(UTC),
            created_by=created_by,
            payload=payload,
        )
        saved = questions_repo.insert(question, db_path=db_path)

        if dedup_vector is not None and not dedup_result.is_duplicate:
            dedup.record_question_embedding(
                question_id=saved.id,
                question_version=saved.version,
                topic=saved.topic,
                vector=dedup_vector,
                vector_store=dedup_vector_store,
            )

        return saved

    raise GenerationError(
        f"Failed to generate a valid {question_type.value} question for topic={topic!r} "
        f"after {MAX_ATTEMPTS} attempts: {last_error}"
    )


def _parse_mcq_response(text: str) -> tuple[str, McqPayload]:
    data = json.loads(text)
    stem = data["stem"]
    payload = McqPayload(
        options=data["options"],
        correct_option_id=data["correct_option_id"],
        explanation=data["explanation"],
    )
    return stem, payload


def _parse_true_false_response(text: str) -> tuple[str, TrueFalsePayload]:
    data = json.loads(text)
    stem = data["stem"]
    payload = TrueFalsePayload(
        correct_answer=data["correct_answer"],
        explanation=data["explanation"],
    )
    return stem, payload


def _parse_fill_blank_response(text: str) -> tuple[str, FillBlankPayload]:
    data = json.loads(text)
    stem = data["stem"]
    if stem.count("___") != 1:
        raise ValueError(
            f"stem must contain exactly one '___' blank marker, found {stem.count('___')}"
        )
    payload = FillBlankPayload(
        accepted_answers=data["accepted_answers"],
        blank_marker="___",
        explanation=data["explanation"],
        case_sensitive=data.get("case_sensitive", False),
    )
    return stem, payload

