from core.enums import QuestionStatus
from db.repositories import questions_repo
from tests.factories import make_fill_blank_question, make_mcq_question


def test_insert_and_get_round_trips(db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)

    fetched = questions_repo.get(question.id, question.version, db_path=db_path)

    assert fetched == question


def test_get_missing_returns_none(db_path):
    assert questions_repo.get("does-not-exist", 1, db_path=db_path) is None


def test_get_latest_returns_highest_version(db_path):
    original = make_mcq_question()
    questions_repo.insert(original, db_path=db_path)
    edited = questions_repo.insert_new_version(
        base=original,
        payload=original.payload,
        created_by="sme_1",
        parent_id=original.id,
        parent_version=original.version,
        db_path=db_path,
    )

    latest = questions_repo.get_latest(original.id, db_path=db_path)

    assert latest.version == 2
    assert latest == edited


def test_list_filters_by_topic_status_type(db_path):
    mcq = make_mcq_question(topic="geography", status=QuestionStatus.APPROVED)
    fill_blank = make_fill_blank_question(topic="geography")
    other_topic = make_mcq_question(topic="history")
    for q in (mcq, fill_blank, other_topic):
        questions_repo.insert(q, db_path=db_path)

    results = questions_repo.list_questions(topic="geography", db_path=db_path)
    assert {q.id for q in results} == {mcq.id, fill_blank.id}

    approved_only = questions_repo.list_questions(
        status=QuestionStatus.APPROVED, db_path=db_path
    )
    assert {q.id for q in approved_only} == {mcq.id}


def test_update_status(db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)

    questions_repo.update_status(
        question.id, question.version, QuestionStatus.APPROVED, db_path=db_path
    )

    fetched = questions_repo.get(question.id, question.version, db_path=db_path)
    assert fetched.status == QuestionStatus.APPROVED


def test_insert_new_version_is_append_only_not_an_update(db_path):
    original = make_mcq_question()
    questions_repo.insert(original, db_path=db_path)

    edited_payload = original.payload.model_copy(
        update={"explanation": "Corrected explanation."}
    )
    questions_repo.insert_new_version(
        base=original,
        payload=edited_payload,
        created_by="sme_1",
        parent_id=original.id,
        parent_version=original.version,
        db_path=db_path,
    )

    original_row = questions_repo.get(original.id, 1, db_path=db_path)
    new_row = questions_repo.get(original.id, 2, db_path=db_path)

    assert original_row.payload.explanation == "Paris is the capital of France."
    assert new_row.payload.explanation == "Corrected explanation."
    assert new_row.parent_id == original.id
    assert new_row.parent_version == 1
