from api.deps import get_llm_provider_dep
from api.main import app
from core.enums import QuestionStatus
from db.repositories import questions_repo
from tests.factories import FakeLLMProvider, make_judge_scores_json, make_llm_result, make_mcq_question


def test_create_evaluation_returns_evaluation_and_updates_status(client, db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider(
        [make_llm_result(text=make_judge_scores_json())]
    )

    response = client.post(
        "/evaluations",
        json={"question_id": question.id, "question_version": question.version},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["question_id"] == question.id
    assert body["overall_verdict"] == "pass"

    updated = questions_repo.get(question.id, question.version, db_path=db_path)
    assert updated.status == QuestionStatus.PENDING_REVIEW


def test_create_evaluation_question_not_found_returns_404(client):
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider([])

    response = client.post(
        "/evaluations",
        json={"question_id": "does-not-exist", "question_version": 1},
    )

    assert response.status_code == 404


def test_list_evaluations_returns_history(client, db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider(
        [make_llm_result(text=make_judge_scores_json())]
    )
    client.post(
        "/evaluations",
        json={"question_id": question.id, "question_version": question.version},
    )

    response = client.get(f"/evaluations/{question.id}")

    assert response.status_code == 200
    assert len(response.json()) == 1
