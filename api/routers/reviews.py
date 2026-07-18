from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db_path
from api.schemas import SubmitReviewRequest
from core.models import Review
from db.repositories import questions_repo, reviews_repo
from services.review import ReviewError, submit_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=Review)
def create_review(body: SubmitReviewRequest, db_path: Path = Depends(get_db_path)):
    question = questions_repo.get(body.question_id, body.question_version, db_path=db_path)
    if question is None:
        raise HTTPException(
            404, f"No question found for id={body.question_id!r} version={body.question_version}"
        )
    try:
        return submit_review(
            question_id=body.question_id,
            question_version=body.question_version,
            reviewer_id=body.reviewer_id,
            decision=body.decision,
            feedback=body.feedback,
            edited_payload=body.edited_payload,
            db_path=db_path,
        )
    except ReviewError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{question_id}", response_model=list[Review])
def list_reviews(question_id: str, db_path: Path = Depends(get_db_path)):
    return reviews_repo.list_for_question(question_id, db_path=db_path)
