from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.rubric import TRUE_FALSE_RUBRIC_V1
from db.connection import init_db
from db.repositories import questions_repo
from tests.factories import (
    FakeLLMProvider,
    make_judge_scores_json,
    make_llm_result,
    make_true_false_question,
)

EVALUATE_PAGE = Path(__file__).resolve().parents[2] / "app" / "pages" / "3_evaluate.py"


def test_evaluate_page_shows_empty_state_when_no_questions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")

    at = AppTest.from_file(str(EVALUATE_PAGE))
    at.run()

    assert not at.exception
    assert len(at.info) == 1


def test_evaluate_page_lists_and_evaluates_non_mcq_question(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    questions_repo.insert(make_true_false_question())
    monkeypatch.setattr(
        "services.evaluation.get_llm_provider",
        lambda *a, **k: FakeLLMProvider(
            [make_llm_result(text=make_judge_scores_json(rubric=TRUE_FALSE_RUBRIC_V1))]
        ),
    )

    at = AppTest.from_file(str(EVALUATE_PAGE))
    at.run()
    at.button(key="evaluate_button").click().run()

    assert not at.exception
    assert any("PASS" in s.value for s in at.success)
