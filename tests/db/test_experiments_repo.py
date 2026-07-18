from db.repositories import experiments_repo, questions_repo
from tests.factories import make_experiment, make_experiment_run, make_mcq_question


def test_insert_and_get_experiment(db_path):
    experiment = make_experiment()
    experiments_repo.insert(experiment, db_path=db_path)

    fetched = experiments_repo.get(experiment.id, db_path=db_path)

    assert fetched == experiment


def test_insert_and_list_runs(db_path):
    experiment = make_experiment()
    experiments_repo.insert(experiment, db_path=db_path)
    question = make_mcq_question()
    questions_repo.insert(question, db_path=db_path)
    run = make_experiment_run(experiment, question)

    experiments_repo.insert_run(run, db_path=db_path)

    results = experiments_repo.list_runs(experiment.id, db_path=db_path)
    assert results == [run]
