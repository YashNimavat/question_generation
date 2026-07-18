import json

from api.deps import get_embedding_provider_dep, get_llm_provider_dep
from api.main import app
from tests.factories import FakeLLMProvider, make_judge_scores_json, make_llm_result

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


def _experiment_request(**overrides):
    body = {
        "name": "model-comparison",
        "hypothesis": "Model B produces fewer weak distractors than Model A.",
        "variants": [{"key": "a", "model": "model-a"}, {"key": "b", "model": "model-b"}],
        "topic": "geography",
        "difficulty": "easy",
        "sample_size": 1,
    }
    body.update(overrides)
    return body


def test_create_experiment_runs_variants_and_returns_complete_experiment(client):
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider(
        [
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=make_judge_scores_json()),
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=make_judge_scores_json()),
        ]
    )
    app.dependency_overrides[get_embedding_provider_dep] = lambda: None

    response = client.post("/experiments", json=_experiment_request())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert len(body["variants"]) == 2


def test_create_experiment_single_variant_returns_422(client):
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider([])
    app.dependency_overrides[get_embedding_provider_dep] = lambda: None

    response = client.post(
        "/experiments", json=_experiment_request(variants=[{"key": "a", "model": "model-a"}])
    )

    assert response.status_code == 422


def test_get_experiment_results_returns_per_variant_metrics(client):
    app.dependency_overrides[get_llm_provider_dep] = lambda: FakeLLMProvider(
        [
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=make_judge_scores_json()),
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=make_judge_scores_json()),
        ]
    )
    app.dependency_overrides[get_embedding_provider_dep] = lambda: None
    created = client.post("/experiments", json=_experiment_request()).json()

    response = client.get(f"/experiments/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"a", "b"}
    assert body["a"]["run_count"] == 1
    assert body["a"]["pass_rate"] == 1.0


def test_get_experiment_results_not_found_returns_404(client):
    response = client.get("/experiments/does-not-exist")

    assert response.status_code == 404
