import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from config.settings import settings
from core.enums import OperationType, QuestionStatus, Source
from core.models import McqPayload, McqQuestion
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

PROMPT_VERSION = "mcq_v1"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "mcq_v1.txt"
GROUNDED_PROMPT_VERSION = "mcq_grounded_v1"
GROUNDED_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "mcq_grounded_v1.txt"
MAX_ATTEMPTS = 2


class GenerationError(Exception):
    pass


def generate_mcq(
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
) -> McqQuestion:
    provider = provider or get_llm_provider()
    model = model or settings.default_llm_model

    rag_usage: dict | None = None
    if document_id is not None:
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
        prompt_path = GROUNDED_PROMPT_PATH
        prompt_version = GROUNDED_PROMPT_VERSION
        user_content = (
            f"Topic: {topic}\nDifficulty: {difficulty}\n\n"
            f"Source material:\n{build_grounded_context(chunks)}\n\n"
            "Generate one multiple-choice question now, grounded only in the "
            "source material above."
        )
        rag_usage = {"document_id": document_id, "chunk_ids": [c.chunk_id for c in chunks]}
    else:
        prompt_path = PROMPT_PATH
        prompt_version = PROMPT_VERSION
        user_content = (
            f"Topic: {topic}\nDifficulty: {difficulty}\n"
            "Generate one multiple-choice question now."
        )

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
            stem, payload = _parse_mcq_response(result.text)
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
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
        question = McqQuestion(
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
        f"Failed to generate a valid MCQ for topic={topic!r} after "
        f"{MAX_ATTEMPTS} attempts: {last_error}"
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
