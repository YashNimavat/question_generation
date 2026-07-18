from core.enums import ReasonCategory, ReviewDecision
from db.repositories import questions_repo, reviews_repo
from tests.factories import make_mcq_question, make_review


def test_insert_and_list_for_question(db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    review = make_review(question)

    reviews_repo.insert(review, db_path=db_path)

    results = reviews_repo.list_for_question(question.id, db_path=db_path)
    assert results == [review]


def test_reject_review_round_trips_reason_category(db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    review = make_review(
        question,
        decision=ReviewDecision.REJECT,
        reason_category=ReasonCategory.WEAK_DISTRACTORS,
        comment="Third distractor is off-topic.",
    )

    reviews_repo.insert(review, db_path=db_path)

    [fetched] = reviews_repo.list_for_question(question.id, db_path=db_path)
    assert fetched.reason_category == ReasonCategory.WEAK_DISTRACTORS
    assert fetched.comment == "Third distractor is off-topic."
