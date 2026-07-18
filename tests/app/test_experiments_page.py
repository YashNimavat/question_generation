import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from db.connection import init_db
from tests.factories import FakeLLMProvider, make_judge_scores_json, make_llm_result

EXPERIMENTS_PAGE = Path(__file__).resolve().parents[2] / "app" / "pages" / "6_experiments.py"

# tests/conftest.py's autouse _no_real_secrets fixture leaves no cohere_api_key
# configured, so services.dedup's embedding calls are skipped gracefully here
# unless a test explicitly injects a FakeEmbeddingProvider.

VALID_MCQ_JSON = json.dumps(
    {
        "stem": "What is the capital of France?",
        "options": [
            {"id": "A", "text": "Paris", "is_correct": True},
            {"id": "B", "text": "Lyon", "is_correct": False},
            {"id": "C", "text": "Nice", "is_correct": False},
        ],
        "correct_option_id": "A",
        "explanation": "Paris has been the capital of France since the 10th century.",
    }
)
PASSING_JUDGE_JSON = make_judge_scores_json()


def test_experiments_page_shows_empty_state_when_no_experiments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")

    at = AppTest.from_file(str(EXPERIMENTS_PAGE))
    at.run(timeout=15)

    assert not at.exception
    assert len(at.caption) >= 1


def test_experiments_page_runs_a_model_comparison_and_renders_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")

    # 2 variants x 1 sample each = 2 samples -> 4 provider.generate calls
    # (generate, evaluate) x (variant a, variant b), in that order.
    shared_provider = FakeLLMProvider(
        [
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=PASSING_JUDGE_JSON),
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=PASSING_JUDGE_JSON),
        ]
    )
    monkeypatch.setattr("services.generation.get_llm_provider", lambda *a, **k: shared_provider)
    monkeypatch.setattr("services.evaluation.get_llm_provider", lambda *a, **k: shared_provider)

    at = AppTest.from_file(str(EXPERIMENTS_PAGE))
    at.run(timeout=15)

    at.text_input(key="experiment_name").input("model comparison").run(timeout=15)
    at.text_input(key="experiment_hypothesis").input("model b is better").run(timeout=15)
    at.text_input(key="experiment_topic").input("geography").run(timeout=15)
    at.number_input(key="experiment_sample_size").set_value(1).run(timeout=15)

    at.button(key="run_experiment_button").click().run(timeout=15)

    assert not at.exception
    assert len(shared_provider.calls) == 4
    # comparison metrics rendered for both variants
    metric_labels = {m.label for m in at.metric}
    assert "Questions generated" in metric_labels
    assert "Pass rate" in metric_labels

    # the experiment now shows up in the past-experiments picker too
    assert any("model comparison" in opt for opt in at.selectbox(key="past_experiment_select").options)
