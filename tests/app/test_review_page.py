from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.enums import QuestionStatus, ReviewDecision
from db.connection import init_db
from db.repositories import questions_repo
from tests.factories import make_fill_blank_question, make_mcq_question, make_true_false_question

REVIEW_PAGE = Path(__file__).resolve().parents[2] / "app" / "pages" / "4_review.py"


def test_review_page_shows_empty_state_when_queue_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")

    at = AppTest.from_file(str(REVIEW_PAGE))
    at.run()

    assert not at.exception
    assert len(at.info) == 1


def test_review_page_approve_marks_question_approved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    question = questions_repo.insert(
        make_mcq_question(status=QuestionStatus.PENDING_REVIEW)
    )

    at = AppTest.from_file(str(REVIEW_PAGE))
    at.run()
    at.text_input(key="review_reviewer_id").input("sme_1").run()
    at.radio(key="review_decision").set_value(ReviewDecision.APPROVE).run()
    at.button(key="review_submit_button").click().run()

    assert not at.exception
    assert any("approve" in s.value for s in at.success)
    updated = questions_repo.get(question.id, question.version)
    assert updated.status == QuestionStatus.APPROVED


def test_review_page_reject_requires_reviewer_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    question = questions_repo.insert(
        make_mcq_question(status=QuestionStatus.PENDING_REVIEW)
    )

    at = AppTest.from_file(str(REVIEW_PAGE))
    at.run()
    at.radio(key="review_decision").set_value(ReviewDecision.REJECT).run()
    at.button(key="review_submit_button").click().run()

    assert not at.exception
    assert len(at.warning) == 1
    unchanged = questions_repo.get(question.id, question.version)
    assert unchanged.status == QuestionStatus.PENDING_REVIEW


def test_review_page_edit_creates_new_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    question = questions_repo.insert(
        make_mcq_question(status=QuestionStatus.PENDING_REVIEW)
    )

    at = AppTest.from_file(str(REVIEW_PAGE))
    at.run()
    at.text_input(key="review_reviewer_id").input("sme_1").run()
    at.radio(key="review_decision").set_value(ReviewDecision.EDIT).run()
    at.text_area(key="review_edit_explanation").input("Corrected explanation.").run()
    at.button(key="review_submit_button").click().run()

    assert not at.exception
    assert any("edit" in s.value for s in at.success)
    original = questions_repo.get(question.id, 1)
    assert original.status == QuestionStatus.EDITED
    new_version = questions_repo.get(question.id, 2)
    assert new_version is not None
    assert new_version.payload.explanation == "Corrected explanation."


def test_review_page_edit_true_false_creates_new_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    question = questions_repo.insert(
        make_true_false_question(status=QuestionStatus.PENDING_REVIEW)
    )

    at = AppTest.from_file(str(REVIEW_PAGE))
    at.run()
    at.text_input(key="review_reviewer_id").input("sme_1").run()
    at.radio(key="review_decision").set_value(ReviewDecision.EDIT).run()
    at.radio(key="review_edit_correct_answer").set_value(False).run()
    at.text_area(key="review_edit_tf_explanation").input("Actually false.").run()
    at.button(key="review_submit_button").click().run()

    assert not at.exception
    assert any("edit" in s.value for s in at.success)
    original = questions_repo.get(question.id, 1)
    assert original.status == QuestionStatus.EDITED
    new_version = questions_repo.get(question.id, 2)
    assert new_version is not None
    assert new_version.payload.correct_answer is False
    assert new_version.payload.explanation == "Actually false."


def test_review_page_edit_fill_blank_creates_new_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    question = questions_repo.insert(
        make_fill_blank_question(status=QuestionStatus.PENDING_REVIEW)
    )

    at = AppTest.from_file(str(REVIEW_PAGE))
    at.run()
    at.text_input(key="review_reviewer_id").input("sme_1").run()
    at.radio(key="review_decision").set_value(ReviewDecision.EDIT).run()
    at.text_input(key="review_edit_accepted_answers").input(
        "mitochondria, the mitochondrion"
    ).run()
    at.text_area(key="review_edit_fill_blank_explanation").input(
        "Corrected: mitochondria produce ATP via oxidative phosphorylation."
    ).run()
    at.button(key="review_submit_button").click().run()

    assert not at.exception
    assert any("edit" in s.value for s in at.success)
    original = questions_repo.get(question.id, 1)
    assert original.status == QuestionStatus.EDITED
    new_version = questions_repo.get(question.id, 2)
    assert new_version is not None
    assert new_version.payload.accepted_answers == ["mitochondria", "the mitochondrion"]
    assert (
        new_version.payload.explanation
        == "Corrected: mitochondria produce ATP via oxidative phosphorylation."
    )
