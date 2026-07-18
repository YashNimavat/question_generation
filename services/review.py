import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from core.enums import QuestionStatus, ReviewDecision
from core.models import Review, ReviewFeedback
from db.connection import DEFAULT_DB_PATH
from db.repositories import questions_repo, reviews_repo


class ReviewError(Exception):
    pass


def submit_review(
    question_id: str,
    question_version: int,
    reviewer_id: str,
    decision: ReviewDecision,
    feedback: ReviewFeedback,
    edited_payload: dict | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> Review:
    original = questions_repo.get(question_id, question_version, db_path=db_path)
    if original is None:
        raise ReviewError(
            f"No question found for id={question_id!r} version={question_version}"
        )
    if decision != ReviewDecision.APPROVE and feedback.reason_category is None:
        raise ReviewError("reason_category is required unless decision is 'approve'")

    linked_new_version: int | None = None
    if decision == ReviewDecision.EDIT:
        if edited_payload is None:
            raise ReviewError("edited_payload is required when decision is 'edit'")
        try:
            new_payload = type(original.payload)(**edited_payload)
        except ValidationError as exc:
            raise ReviewError(f"Edited payload is invalid: {exc}") from exc

        new_question = questions_repo.insert_new_version(
            base=original,
            payload=new_payload,
            created_by=reviewer_id,
            parent_id=original.id,
            parent_version=original.version,
            db_path=db_path,
        )
        questions_repo.update_status(
            question_id, question_version, QuestionStatus.EDITED, db_path=db_path
        )
        linked_new_version = new_question.version
    else:
        new_status = (
            QuestionStatus.APPROVED
            if decision == ReviewDecision.APPROVE
            else QuestionStatus.REJECTED
        )
        questions_repo.update_status(
            question_id, question_version, new_status, db_path=db_path
        )

    review = Review(
        id=str(uuid.uuid4()),
        question_id=question_id,
        question_version=question_version,
        reviewer_id=reviewer_id,
        decision=decision,
        reason_category=feedback.reason_category,
        comment=feedback.comment,
        severity=feedback.severity,
        linked_new_version=linked_new_version,
        created_at=datetime.now(UTC),
    )
    return reviews_repo.insert(review, db_path=db_path)
