from core.enums import DocumentStatus
from db.repositories import documents_repo
from tests.factories import make_document


def test_insert_and_get_round_trips(db_path):
    document = make_document()
    documents_repo.insert(document, db_path=db_path)

    fetched = documents_repo.get(document.id, db_path=db_path)

    assert fetched == document


def test_get_missing_returns_none(db_path):
    assert documents_repo.get("does-not-exist", db_path=db_path) is None


def test_update_status_with_chunk_count(db_path):
    document = make_document()
    documents_repo.insert(document, db_path=db_path)

    documents_repo.update_status(
        document.id, DocumentStatus.READY, chunk_count=12, db_path=db_path
    )

    fetched = documents_repo.get(document.id, db_path=db_path)
    assert fetched.status == DocumentStatus.READY
    assert fetched.chunk_count == 12


def test_list_all_returns_documents_newest_first(db_path):
    from datetime import UTC, datetime, timedelta

    older = make_document(created_at=datetime.now(UTC) - timedelta(hours=1))
    newer = make_document(created_at=datetime.now(UTC))
    documents_repo.insert(older, db_path=db_path)
    documents_repo.insert(newer, db_path=db_path)

    documents = documents_repo.list_all(db_path=db_path)

    assert [d.id for d in documents] == [newer.id, older.id]


def test_list_all_empty_returns_empty_list(db_path):
    assert documents_repo.list_all(db_path=db_path) == []
