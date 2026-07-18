import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from config.settings import settings
from core.enums import OperationType, Source
from core.models import McqPayload, McqQuestion
from db.connection import DEFAULT_DB_PATH
from db.repositories import questions_repo
from llm.base import LLMProvider, Message
from llm.registry import get_llm_provider
from metadata.logger import log_call

PROMPT_VERSION = "mcq_v1"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "mcq_v1.txt"
MAX_ATTEMPTS = 2


class GenerationError(Exception):
    pass


def generate_mcq(
    topic: str,
    difficulty: str,
    provider: LLMProvider | None = None,
    model: str | None = None,
    created_by: str = "system",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> McqQuestion:
    provider = provider or get_llm_provider()
    model = model or settings.default_llm_model

    messages = [
        Message(role="system", content=PROMPT_PATH.read_text()),
        Message(
            role="user",
            content=(
                f"Topic: {topic}\nDifficulty: {difficulty}\n"
                "Generate one multiple-choice question now."
            ),
        ),
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
            prompt_version=PROMPT_VERSION,
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

        question = McqQuestion(
            id=str(uuid.uuid4()),
            version=1,
            stem=stem,
            difficulty=difficulty,
            topic=topic,
            source=Source.TOPIC,
            generation_metadata_id=metadata_record.id,
            created_at=datetime.now(UTC),
            created_by=created_by,
            payload=payload,
        )
        return questions_repo.insert(question, db_path=db_path)

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
