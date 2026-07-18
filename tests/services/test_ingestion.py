from io import BytesIO

import pytest
from docx import Document as DocxDocument

import services.ingestion as ingestion_module
from core.enums import DocumentStatus
from db.connection import get_connection
from db.repositories import documents_repo
from services.ingestion import IngestionError, ingest_document
from tests.factories import FakeEmbeddingProvider, FakeVectorStore, make_embedding_result


def _docx_bytes(paragraphs: list[str]) -> bytes:
    doc = DocxDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


class _FakePdfPage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakePdfReader:
    def __init__(self, stream) -> None:
        self.pages = [_FakePdfPage("Photosynthesis converts light into chemical energy.")]


def test_ingest_docx_happy_path_persists_document_and_vectors(db_path):
    file_bytes = _docx_bytes(
        ["Cell biology is the study of cells.", "Mitochondria produce ATP."]
    )
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[0.1, 0.2]])])
    vector_store = FakeVectorStore()

    document = ingest_document(
        file_bytes=file_bytes,
        filename="notes.docx",
        title="Cell Biology",
        topic="biology",
        tags=["science"],
        embedding_provider=embedding_provider,
        embedding_model="embed-english-v3.0",
        vector_store=vector_store,
        db_path=db_path,
    )

    assert document.status == DocumentStatus.READY
    assert document.chunk_count == 1
    assert document.topic == "biology"
    assert document.tags == ["science"]

    stored = documents_repo.get(document.id, db_path=db_path)
    assert stored == document

    assert len(embedding_provider.calls) == 1
    assert len(vector_store.added) == 1
    assert vector_store.added[0]["ids"] == [f"{document.id}_0"]

    with get_connection(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM metadata_logs WHERE operation_type = 'embedding'"
        ).fetchone()[0]
    assert count == 1


def test_ingest_pdf_happy_path_dispatches_to_pdf_extractor(db_path, monkeypatch):
    monkeypatch.setattr(ingestion_module, "PdfReader", _FakePdfReader)
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=[[0.5, 0.5]])])

    document = ingest_document(
        file_bytes=b"irrelevant-bytes",
        filename="notes.pdf",
        title="Photosynthesis",
        embedding_provider=embedding_provider,
        vector_store=FakeVectorStore(),
        db_path=db_path,
    )

    assert document.status == DocumentStatus.READY
    assert document.chunk_count == 1


def test_ingest_document_rejects_unsupported_extension(db_path):
    with pytest.raises(IngestionError, match="Unsupported file type"):
        ingest_document(
            file_bytes=b"hello",
            filename="notes.txt",
            title="Notes",
            embedding_provider=FakeEmbeddingProvider([]),
            vector_store=FakeVectorStore(),
            db_path=db_path,
        )

    assert documents_repo.list_all(db_path=db_path) == []


def test_ingest_document_garbage_pdf_raises_before_any_db_write(db_path):
    with pytest.raises(IngestionError):
        ingest_document(
            file_bytes=b"not a real pdf",
            filename="broken.pdf",
            title="Broken",
            embedding_provider=FakeEmbeddingProvider([]),
            vector_store=FakeVectorStore(),
            db_path=db_path,
        )

    assert documents_repo.list_all(db_path=db_path) == []


def test_ingest_document_missing_embedding_provider_config_raises_before_db_write(
    db_path, monkeypatch
):
    def _raise_missing_key(provider_name=None):
        raise ValueError("No cohere_api_key configured")

    monkeypatch.setattr(ingestion_module, "get_embedding_provider", _raise_missing_key)
    file_bytes = _docx_bytes(["Some content here."])

    with pytest.raises(IngestionError, match="Embedding provider unavailable"):
        ingest_document(
            file_bytes=file_bytes,
            filename="notes.docx",
            title="Notes",
            vector_store=FakeVectorStore(),
            db_path=db_path,
        )

    assert documents_repo.list_all(db_path=db_path) == []


def test_ingest_document_embedding_failure_marks_document_failed(db_path):
    file_bytes = _docx_bytes(["Some content here."])
    embedding_provider = FakeEmbeddingProvider([])  # no queued results -> raises on call

    with pytest.raises(IngestionError, match="Ingestion failed"):
        ingest_document(
            file_bytes=file_bytes,
            filename="notes.docx",
            title="Notes",
            embedding_provider=embedding_provider,
            vector_store=FakeVectorStore(),
            db_path=db_path,
        )

    documents = documents_repo.list_all(db_path=db_path)
    assert len(documents) == 1
    assert documents[0].status == DocumentStatus.FAILED
