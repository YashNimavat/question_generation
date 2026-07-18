from core.enums import QuestionStatus
from db.repositories import questions_repo
from tests.factories import make_mcq_question


def test_create_review_approve_updates_question_status(client, db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)

    response = client.post(
        "/reviews",
        json={
            "question_id": question.id,
            "question_version": question.version,
            "reviewer_id": "sme_1",
            "decision": "approve",
        },
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "approve"
    updated = questions_repo.get(question.id, question.version, db_path=db_path)
    assert updated.status == QuestionStatus.APPROVED


def test_create_review_reject_without_reason_category_returns_422(client, db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)

    response = client.post(
        "/reviews",
        json={
            "question_id": question.id,
            "question_version": question.version,
            "reviewer_id": "sme_1",
            "decision": "reject",
        },
    )

    assert response.status_code == 422


def test_create_review_edit_inserts_new_question_version(client, db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    edited_payload = question.payload.model_dump(mode="json")
    edited_payload["explanation"] = "A corrected, more specific explanation."

    response = client.post(
        "/reviews",
        json={
            "question_id": question.id,
            "question_version": question.version,
            "reviewer_id": "sme_1",
            "decision": "edit",
            "feedback": {"reason_category": "formatting_issue"},
            "edited_payload": edited_payload,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["linked_new_version"] == 2
    new_version = questions_repo.get(question.id, 2, db_path=db_path)
    assert new_version.payload.explanation == "A corrected, more specific explanation."


def test_create_review_question_not_found_returns_404(client):
    response = client.post(
        "/reviews",
        json={
            "question_id": "does-not-exist",
            "question_version": 1,
            "reviewer_id": "sme_1",
            "decision": "approve",
        },
    )

    assert response.status_code == 404


def test_list_reviews_returns_history(client, db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    client.post(
        "/reviews",
        json={
            "question_id": question.id,
            "question_version": question.version,
            "reviewer_id": "sme_1",
            "decision": "approve",
        },
    )

    response = client.get(f"/reviews/{question.id}")

    assert response.status_code == 200
    assert len(response.json()) == 1
