import json

import pytest

from core.enums import QuestionStatus, Source
from db.connection import get_connection
from db.repositories import metadata_repo, questions_repo
from services.generation import GenerationError, generate_mcq
from tests.factories import FakeLLMProvider, make_llm_result

VALID_MCQ_JSON = json.dumps(
    {
        "stem": "What is the capital of France?",
        "options": [
            {"id": "A", "text": "Paris", "is_correct": True},
            {"id": "B", "text": "Lyon", "is_correct": False},
            {"id": "C", "text": "Nice", "is_correct": False},
            {"id": "D", "text": "Marseille", "is_correct": False},
        ],
        "correct_option_id": "A",
        "explanation": "Paris has been the capital of France since the 10th century.",
    }
)


def test_generate_mcq_happy_path_persists_question_and_metadata(db_path):
    provider = FakeLLMProvider([make_llm_result(text=VALID_MCQ_JSON)])

    question = generate_mcq(
        topic="geography", difficulty="easy", provider=provider, model="llama-3.3-70b-versatile", db_path=db_path
    )

    assert question.status == QuestionStatus.GENERATED
    assert question.source == Source.TOPIC
    assert question.stem == "What is the capital of France?"
    assert question.payload.correct_option_id == "A"
    assert len(provider.calls) == 1

    stored = questions_repo.get(question.id, question.version, db_path=db_path)
    assert stored == question

    metadata_record = metadata_repo.get(question.generation_metadata_id, db_path=db_path)
    assert metadata_record is not None
    assert metadata_record.prompt_version == "mcq_v1"


def test_generate_mcq_retries_once_on_malformed_json_then_succeeds(db_path):
    provider = FakeLLMProvider(
        [
            make_llm_result(text="not json"),
            make_llm_result(text=VALID_MCQ_JSON),
        ]
    )

    question = generate_mcq(topic="geography", difficulty="easy", provider=provider, db_path=db_path)

    assert question.stem == "What is the capital of France?"
    assert len(provider.calls) == 2


def test_generate_mcq_fails_after_two_malformed_attempts(db_path):
    provider = FakeLLMProvider(
        [
            make_llm_result(text="not json"),
            make_llm_result(text="still not json"),
        ]
    )

    with pytest.raises(GenerationError):
        generate_mcq(topic="geography", difficulty="easy", provider=provider, db_path=db_path)

    assert len(provider.calls) == 2
    assert questions_repo.list_questions(topic="geography", db_path=db_path) == []

    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM metadata_logs").fetchone()[0]
    assert count == 2
