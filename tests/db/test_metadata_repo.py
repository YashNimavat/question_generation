from db.repositories import metadata_repo
from tests.factories import make_metadata_record


def test_insert_and_get_round_trips(db_path):
    record = make_metadata_record()

    metadata_repo.insert(record, db_path=db_path)

    fetched = metadata_repo.get(record.id, db_path=db_path)
    assert fetched == record


def test_rag_usage_round_trips_when_present(db_path):
    record = make_metadata_record(
        rag_usage={"document_id": "doc-1", "chunk_ids": ["c1", "c2"]}
    )

    metadata_repo.insert(record, db_path=db_path)

    fetched = metadata_repo.get(record.id, db_path=db_path)
    assert fetched.rag_usage == {"document_id": "doc-1", "chunk_ids": ["c1", "c2"]}


def test_get_missing_returns_none(db_path):
    assert metadata_repo.get("does-not-exist", db_path=db_path) is None
