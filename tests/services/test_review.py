import pytest

from core.enums import QuestionStatus, ReasonCategory, ReviewDecision, Severity
from core.models import ReviewFeedback
from db.repositories import questions_repo, reviews_repo
from services.review import ReviewError, submit_review
from tests.factories import make_mcq_question


def _persisted_question(db_path, **overrides):
    return questions_repo.insert(
        make_mcq_question(status=QuestionStatus.PENDING_REVIEW, **overrides),
        db_path=db_path,
    )


def test_approve_marks_question_approved_and_records_review(db_path):
    question = _persisted_question(db_path)

    review = submit_review(
        question_id=question.id,
        question_version=question.version,
        reviewer_id="sme_1",
        decision=ReviewDecision.APPROVE,
        feedback=ReviewFeedback(),
        db_path=db_path,
    )

    assert review.linked_new_version is None
    updated = questions_repo.get(question.id, question.version, db_path=db_path)
    assert updated.status == QuestionStatus.APPROVED
    assert reviews_repo.list_for_question(question.id, db_path=db_path) == [review]


def test_reject_requires_reason_category(db_path):
    question = _persisted_question(db_path)

    with pytest.raises(ReviewError):
        submit_review(
            question_id=question.id,
            question_version=question.version,
            reviewer_id="sme_1",
            decision=ReviewDecision.REJECT,
            feedback=ReviewFeedback(),
            db_path=db_path,
        )

    unchanged = questions_repo.get(question.id, question.version, db_path=db_path)
    assert unchanged.status == QuestionStatus.PENDING_REVIEW
    assert reviews_repo.list_for_question(question.id, db_path=db_path) == []


def test_reject_with_reason_marks_question_rejected(db_path):
    question = _persisted_question(db_path)

    review = submit_review(
        question_id=question.id,
        question_version=question.version,
        reviewer_id="sme_1",
        decision=ReviewDecision.REJECT,
        feedback=ReviewFeedback(
            reason_category=ReasonCategory.WEAK_DISTRACTORS,
            comment="Distractor B is implausible.",
            severity=Severity.MEDIUM,
        ),
        db_path=db_path,
    )

    assert review.reason_category == ReasonCategory.WEAK_DISTRACTORS
    updated = questions_repo.get(question.id, question.version, db_path=db_path)
    assert updated.status == QuestionStatus.REJECTED


def test_edit_creates_new_version_and_links_review(db_path):
    question = _persisted_question(db_path)
    edited_payload = question.payload.model_dump(mode="json")
    edited_payload["explanation"] = "Corrected explanation."

    review = submit_review(
        question_id=question.id,
        question_version=question.version,
        reviewer_id="sme_1",
        decision=ReviewDecision.EDIT,
        feedback=ReviewFeedback(reason_category=ReasonCategory.FORMATTING_ISSUE),
        edited_payload=edited_payload,
        db_path=db_path,
    )

    assert review.linked_new_version == 2

    original = questions_repo.get(question.id, 1, db_path=db_path)
    assert original.status == QuestionStatus.EDITED
    assert original.payload.explanation != "Corrected explanation."

    new_version = questions_repo.get(question.id, 2, db_path=db_path)
    assert new_version.status == QuestionStatus.GENERATED
    assert new_version.payload.explanation == "Corrected explanation."
    assert new_version.parent_id == question.id
    assert new_version.parent_version == 1
    assert new_version.created_by == "sme_1"


def test_edit_requires_edited_payload(db_path):
    question = _persisted_question(db_path)

    with pytest.raises(ReviewError):
        submit_review(
            question_id=question.id,
            question_version=question.version,
            reviewer_id="sme_1",
            decision=ReviewDecision.EDIT,
            feedback=ReviewFeedback(reason_category=ReasonCategory.OTHER),
            db_path=db_path,
        )


def test_edit_with_invalid_payload_raises_without_mutating_question(db_path):
    question = _persisted_question(db_path)

    with pytest.raises(ReviewError):
        submit_review(
            question_id=question.id,
            question_version=question.version,
            reviewer_id="sme_1",
            decision=ReviewDecision.EDIT,
            feedback=ReviewFeedback(reason_category=ReasonCategory.OTHER),
            edited_payload={"options": []},
            db_path=db_path,
        )

    unchanged = questions_repo.get(question.id, question.version, db_path=db_path)
    assert unchanged.status == QuestionStatus.PENDING_REVIEW
    assert questions_repo.get(question.id, 2, db_path=db_path) is None


def test_unknown_question_raises(db_path):
    with pytest.raises(ReviewError):
        submit_review(
            question_id="missing-id",
            question_version=1,
            reviewer_id="sme_1",
            decision=ReviewDecision.APPROVE,
            feedback=ReviewFeedback(),
            db_path=db_path,
        )
