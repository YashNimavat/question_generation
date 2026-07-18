from io import BytesIO

from docx import Document as DocxDocument

from api.deps import get_embedding_provider_dep, get_vector_store_dep
from api.main import app
from core.enums import DocumentStatus
from db.repositories import documents_repo
from tests.factories import FakeEmbeddingProvider, FakeVectorStore, make_document, make_embedding_result


def _docx_bytes(paragraphs: list[str]) -> bytes:
    doc = DocxDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_document_persists_and_returns_ready_document(client, db_path):
    app.dependency_overrides[get_embedding_provider_dep] = lambda: FakeEmbeddingProvider(
        [make_embedding_result(vectors=[[0.1, 0.2]])]
    )
    app.dependency_overrides[get_vector_store_dep] = lambda: FakeVectorStore()
    file_bytes = _docx_bytes(["Mitochondria produce ATP."])

    response = client.post(
        "/documents",
        data={"title": "Cell Biology", "topic": "biology", "tags": "science, cells"},
        files={"file": ("notes.docx", file_bytes)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["tags"] == ["science", "cells"]
    stored = documents_repo.get(body["id"], db_path=db_path)
    assert stored.status == DocumentStatus.READY


def test_upload_document_unsupported_extension_returns_422(client):
    app.dependency_overrides[get_embedding_provider_dep] = lambda: FakeEmbeddingProvider([])
    app.dependency_overrides[get_vector_store_dep] = lambda: FakeVectorStore()

    response = client.post(
        "/documents",
        data={"title": "Notes"},
        files={"file": ("notes.txt", b"plain text")},
    )

    assert response.status_code == 422


def test_get_document_not_found_returns_404(client):
    response = client.get("/documents/does-not-exist")

    assert response.status_code == 404


def test_get_document_returns_stored_document(client, db_path):
    document = make_document()
    documents_repo.insert(document, db_path=db_path)

    response = client.get(f"/documents/{document.id}")

    assert response.status_code == 200
    assert response.json()["id"] == document.id
