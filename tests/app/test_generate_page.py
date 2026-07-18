import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from db.connection import init_db
from tests.factories import FakeEmbeddingProvider, FakeLLMProvider, make_embedding_result, make_llm_result

GENERATE_PAGE = Path(__file__).resolve().parents[2] / "app" / "pages" / "1_generate.py"

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

VALID_TRUE_FALSE_JSON = json.dumps(
    {
        "stem": "Water boils at 100 degrees Celsius at sea level.",
        "correct_answer": True,
        "explanation": "At standard atmospheric pressure, water's boiling point is 100C.",
    }
)

VALID_FILL_BLANK_JSON = json.dumps(
    {
        "stem": "The ___ is the powerhouse of the cell.",
        "accepted_answers": ["mitochondria", "the mitochondria"],
        "explanation": "Mitochondria generate most of the cell's ATP supply.",
        "case_sensitive": False,
    }
)


def test_generate_page_renders_generated_question(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    monkeypatch.setattr(
        "services.generation.get_llm_provider",
        lambda *a, **k: FakeLLMProvider([make_llm_result(text=VALID_MCQ_JSON)]),
    )
    monkeypatch.setattr(
        "services.dedup.get_embedding_provider",
        lambda *a, **k: FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])]),
    )

    at = AppTest.from_file(str(GENERATE_PAGE))
    at.run()
    at.text_input(key="generate_topic").input("geography").run()
    at.button(key="generate_button").click().run()

    assert not at.exception
    assert any("What is the capital of France?" in s.value for s in at.subheader)
    assert any("Paris" in s.value for s in at.success)


def test_generate_page_warns_on_blank_topic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")

    at = AppTest.from_file(str(GENERATE_PAGE))
    at.run()
    at.button(key="generate_button").click().run()

    assert not at.exception
    assert len(at.warning) == 1


def test_generate_page_shows_error_on_generation_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    monkeypatch.setattr(
        "services.generation.get_llm_provider",
        lambda *a, **k: FakeLLMProvider(
            [make_llm_result(text="not json"), make_llm_result(text="still not json")]
        ),
    )

    at = AppTest.from_file(str(GENERATE_PAGE))
    at.run()
    at.text_input(key="generate_topic").input("geography").run()
    at.button(key="generate_button").click().run()

    assert not at.exception
    assert len(at.error) == 1


def test_generate_page_generates_true_false_question(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    monkeypatch.setattr(
        "services.generation.get_llm_provider",
        lambda *a, **k: FakeLLMProvider([make_llm_result(text=VALID_TRUE_FALSE_JSON)]),
    )
    monkeypatch.setattr(
        "services.dedup.get_embedding_provider",
        lambda *a, **k: FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])]),
    )

    at = AppTest.from_file(str(GENERATE_PAGE))
    at.run()
    at.text_input(key="generate_topic").input("science").run()
    at.selectbox(key="generate_question_type").select("True/False").run()
    at.button(key="generate_button").click().run()

    assert not at.exception
    assert any("Water boils at 100 degrees Celsius" in s.value for s in at.subheader)
    assert any("True" in s.value for s in at.success)


def test_generate_page_generates_fill_blank_question(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    monkeypatch.setattr(
        "services.generation.get_llm_provider",
        lambda *a, **k: FakeLLMProvider([make_llm_result(text=VALID_FILL_BLANK_JSON)]),
    )
    monkeypatch.setattr(
        "services.dedup.get_embedding_provider",
        lambda *a, **k: FakeEmbeddingProvider([make_embedding_result(vectors=[[1.0, 0.0]])]),
    )

    at = AppTest.from_file(str(GENERATE_PAGE))
    at.run()
    at.text_input(key="generate_topic").input("biology").run()
    at.selectbox(key="generate_question_type").select("Fill-in-Blank").run()
    at.button(key="generate_button").click().run()

    assert not at.exception
    assert any("powerhouse of the cell" in s.value for s in at.subheader)
    assert any("mitochondria" in s.value for s in at.markdown)
