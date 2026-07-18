import json

from api.deps import get_embedding_provider_dep, get_llm_provider_dep
from api.main import app
from core.enums import QuestionStatus
from db.repositories import questions_repo
from tests.factories import FakeLLMProvider, make_llm_result, make_mcq_question

VALID_MCQ_JSON = json.dumps(
    {
        "stem": "What is the capital of France?",
        "options": [
            {"id": "A", "text": "Paris", "is_correct": True},
            {"id": "B", "text": "Lyon", "is_correct": False},
        ],
        "correct_option_id": "A",
        "explanation": "Paris has been the capital of France since the 10th century.",
    }
)


def test_generate_mcq_returns_persisted_question(client, db_path):
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider(
        [make_llm_result(text=VALID_MCQ_JSON)]
    )
    app.dependency_overrides[get_embedding_provider_dep] = lambda: None

    response = client.post(
        "/questions/generate",
        json={"type": "mcq", "topic": "geography", "difficulty": "easy"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "mcq"
    assert body["stem"] == "What is the capital of France?"
    assert questions_repo.get(body["id"], body["version"], db_path=db_path) is not None


def test_generate_prompt_version_rejected_for_non_mcq_type(client):
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider([])
    app.dependency_overrides[get_embedding_provider_dep] = lambda: None

    response = client.post(
        "/questions/generate",
        json={
            "type": "true_false",
            "topic": "science",
            "difficulty": "easy",
            "prompt_version": "true_false_v2",
        },
    )

    assert response.status_code == 422


def test_generate_returns_422_after_repeated_malformed_json(client):
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider(
        [make_llm_result(text="not json"), make_llm_result(text="still not json")]
    )
    app.dependency_overrides[get_embedding_provider_dep] = lambda: None

    response = client.post(
        "/questions/generate",
        json={"type": "mcq", "topic": "geography", "difficulty": "easy"},
    )

    assert response.status_code == 422


def test_list_questions_filters_by_topic(client, db_path):
    geography = make_mcq_question(topic="geography")
    biology = make_mcq_question(topic="biology")
    questions_repo.insert(geography, db_path=db_path)
    questions_repo.insert(biology, db_path=db_path)

    response = client.get("/questions", params={"topic": "geography"})

    assert response.status_code == 200
    body = response.json()
    assert [q["id"] for q in body] == [geography.id]


def test_get_question_latest_version_by_default(client, db_path):
    original = make_mcq_question(status=QuestionStatus.EDITED)
    questions_repo.insert(original, db_path=db_path)
    edited = questions_repo.insert_new_version(
        base=original,
        payload=original.payload,
        created_by="sme_1",
        parent_id=original.id,
        parent_version=original.version,
        db_path=db_path,
    )

    response = client.get(f"/questions/{original.id}")

    assert response.status_code == 200
    assert response.json()["version"] == edited.version


def test_get_question_specific_version(client, db_path):
    original = make_mcq_question(status=QuestionStatus.EDITED)
    questions_repo.insert(original, db_path=db_path)
    questions_repo.insert_new_version(
        base=original,
        payload=original.payload,
        created_by="sme_1",
        parent_id=original.id,
        parent_version=original.version,
        db_path=db_path,
    )

    response = client.get(f"/questions/{original.id}", params={"version": 1})

    assert response.status_code == 200
    assert response.json()["version"] == 1


def test_get_question_not_found_returns_404(client):
    response = client.get("/questions/does-not-exist")

    assert response.status_code == 404
