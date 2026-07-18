from datetime import UTC, datetime

from core.enums import ExperimentStatus
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


def test_update_status(db_path):
    experiment = make_experiment(status=ExperimentStatus.RUNNING)
    experiments_repo.insert(experiment, db_path=db_path)

    experiments_repo.update_status(experiment.id, ExperimentStatus.COMPLETE, db_path=db_path)

    fetched = experiments_repo.get(experiment.id, db_path=db_path)
    assert fetched.status == ExperimentStatus.COMPLETE


def test_list_all_orders_by_created_at_desc(db_path):
    older = make_experiment(name="older", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    newer = make_experiment(name="newer", created_at=datetime(2026, 6, 1, tzinfo=UTC))
    experiments_repo.insert(older, db_path=db_path)
    experiments_repo.insert(newer, db_path=db_path)

    results = experiments_repo.list_all(db_path=db_path)

    assert [e.name for e in results] == ["newer", "older"]
