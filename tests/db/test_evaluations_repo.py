from db.repositories import evaluations_repo, metadata_repo, questions_repo
from tests.factories import make_evaluation, make_mcq_question, make_metadata_record


def _insert_metadata(db_path):
    record = make_metadata_record()
    metadata_repo.insert(record, db_path=db_path)
    return record.id


def test_insert_and_list_for_question(db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    evaluation = make_evaluation(
        question, evaluation_metadata_id=_insert_metadata(db_path)
    )

    evaluations_repo.insert(evaluation, db_path=db_path)

    results = evaluations_repo.list_for_question(question.id, db_path=db_path)
    assert results == [evaluation]


def test_list_for_question_returns_full_history(db_path):
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    first = make_evaluation(
        question, rubric_version="v1", evaluation_metadata_id=_insert_metadata(db_path)
    )
    second = make_evaluation(
        question, rubric_version="v2", evaluation_metadata_id=_insert_metadata(db_path)
    )
    evaluations_repo.insert(first, db_path=db_path)
    evaluations_repo.insert(second, db_path=db_path)

    results = evaluations_repo.list_for_question(question.id, db_path=db_path)

    assert {e.id for e in results} == {first.id, second.id}
