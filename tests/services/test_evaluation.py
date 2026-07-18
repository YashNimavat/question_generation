import pytest

from core.enums import QuestionStatus
from db.connection import get_connection
from db.repositories import evaluations_repo, questions_repo
from services.evaluation import EvaluationError, evaluate
from tests.factories import FakeLLMProvider, make_judge_scores_json, make_llm_result, make_mcq_question

PASSING_JSON = make_judge_scores_json()
FAILING_JSON = make_judge_scores_json(correctness={"score": 2, "rationale": "Marked option is wrong."})


def _persisted_question(db_path):
    return questions_repo.insert(make_mcq_question(), db_path=db_path)


def test_evaluate_happy_path_persists_evaluation_and_marks_pending_review(db_path):
    question = _persisted_question(db_path)
    provider = FakeLLMProvider([make_llm_result(text=PASSING_JSON)])

    evaluation = evaluate(
        question_id=question.id,
        question_version=question.version,
        provider=provider,
        model="llama-3.1-8b-instant",
        db_path=db_path,
    )

    assert evaluation.overall_verdict.value == "pass"
    assert evaluation.reference_answer_used is False
    assert len(provider.calls) == 1

    stored = evaluations_repo.list_for_question(question.id, db_path=db_path)
    assert stored == [evaluation]

    updated_question = questions_repo.get(question.id, question.version, db_path=db_path)
    assert updated_question.status == QuestionStatus.PENDING_REVIEW


def test_evaluate_fail_verdict_marks_question_rejected(db_path):
    question = _persisted_question(db_path)
    provider = FakeLLMProvider([make_llm_result(text=FAILING_JSON)])

    evaluation = evaluate(
        question_id=question.id, question_version=question.version, provider=provider, db_path=db_path
    )

    assert evaluation.overall_verdict.value == "fail"
    updated_question = questions_repo.get(question.id, question.version, db_path=db_path)
    assert updated_question.status == QuestionStatus.REJECTED


def test_evaluate_records_reference_answer_usage_and_includes_it_in_prompt(db_path):
    question = _persisted_question(db_path)
    provider = FakeLLMProvider([make_llm_result(text=PASSING_JSON)])

    evaluation = evaluate(
        question_id=question.id,
        question_version=question.version,
        reference_answer="Paris",
        provider=provider,
        db_path=db_path,
    )

    assert evaluation.reference_answer_used is True
    user_message = provider.calls[0]["messages"][1]
    assert "Paris" in user_message.content


def test_evaluate_retries_once_on_malformed_json_then_succeeds(db_path):
    question = _persisted_question(db_path)
    provider = FakeLLMProvider(
        [
            make_llm_result(text="not json"),
            make_llm_result(text=PASSING_JSON),
        ]
    )

    evaluation = evaluate(
        question_id=question.id, question_version=question.version, provider=provider, db_path=db_path
    )

    assert evaluation.overall_verdict.value == "pass"
    assert len(provider.calls) == 2


def test_evaluate_fails_after_two_malformed_attempts(db_path):
    question = _persisted_question(db_path)
    provider = FakeLLMProvider(
        [
            make_llm_result(text="not json"),
            make_llm_result(text="still not json"),
        ]
    )

    with pytest.raises(EvaluationError):
        evaluate(question_id=question.id, question_version=question.version, provider=provider, db_path=db_path)

    assert len(provider.calls) == 2
    assert evaluations_repo.list_for_question(question.id, db_path=db_path) == []

    updated_question = questions_repo.get(question.id, question.version, db_path=db_path)
    assert updated_question.status == QuestionStatus.GENERATED

    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM metadata_logs").fetchone()[0]
    assert count == 2


def test_evaluate_unknown_question_raises_without_calling_provider(db_path):
    provider = FakeLLMProvider([])

    with pytest.raises(EvaluationError):
        evaluate(question_id="missing-id", question_version=1, provider=provider, db_path=db_path)

    assert provider.calls == []
