from pathlib import Path

from streamlit.testing.v1 import AppTest

from db.connection import init_db
from db.repositories import questions_repo
from tests.factories import make_fill_blank_question, make_mcq_question, make_true_false_question

QUESTIONS_PAGE = Path(__file__).resolve().parents[2] / "app" / "pages" / "2_questions.py"


def test_questions_page_lists_stored_question(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    questions_repo.insert(make_mcq_question(topic="geography"))

    at = AppTest.from_file(str(QUESTIONS_PAGE))
    at.run()

    assert not at.exception
    assert any("capital of France" in s.value for s in at.subheader)


def test_questions_page_shows_empty_state_for_no_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    questions_repo.insert(make_mcq_question(topic="geography"))

    at = AppTest.from_file(str(QUESTIONS_PAGE))
    at.run()
    at.text_input(key="questions_topic_filter").input("nonexistent-topic").run()

    assert not at.exception
    assert len(at.info) == 1


def test_questions_page_renders_true_false_question(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    questions_repo.insert(make_true_false_question(topic="science"))

    at = AppTest.from_file(str(QUESTIONS_PAGE))
    at.run()

    assert not at.exception
    assert any("Water boils at 100 degrees Celsius" in s.value for s in at.subheader)
    assert any("True" in s.value for s in at.success)


def test_questions_page_renders_fill_blank_question(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    questions_repo.insert(make_fill_blank_question(topic="biology"))

    at = AppTest.from_file(str(QUESTIONS_PAGE))
    at.run()

    assert not at.exception
    assert any("powerhouse of the cell" in s.value for s in at.subheader)
    assert any("mitochondria" in s.value for s in at.markdown)
    assert any("ATP supply" in s.value for s in at.markdown)
