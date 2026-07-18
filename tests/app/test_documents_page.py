from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from streamlit.testing.v1 import AppTest

from config import secrets as secrets_module
from core.enums import DocumentStatus
from db.connection import init_db
from db.repositories import documents_repo
from tests.factories import make_document

DOCUMENTS_PAGE = Path(__file__).resolve().parents[2] / "app" / "pages" / "5_documents.py"


def _docx_bytes(paragraphs: list[str]) -> bytes:
    doc = DocxDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_documents_page_shows_empty_state_when_no_documents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")

    at = AppTest.from_file(str(DOCUMENTS_PAGE))
    at.run()

    assert not at.exception
    assert len(at.info) == 1


def test_documents_page_lists_existing_documents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    documents_repo.insert(make_document(title="Cell Biology 101"))

    at = AppTest.from_file(str(DOCUMENTS_PAGE))
    at.run()

    assert not at.exception
    assert len(at.dataframe) == 1


def test_documents_page_upload_without_title_warns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")

    at = AppTest.from_file(str(DOCUMENTS_PAGE))
    at.run()
    at.file_uploader[0].upload("notes.docx", _docx_bytes(["Some content."])).run()
    at.button(key="documents_ingest_button").click().run()

    assert not at.exception
    assert len(at.warning) == 1
    assert documents_repo.list_all() == []


def test_documents_page_ingest_surfaces_clean_error_without_cohere_key(tmp_path, monkeypatch):
    # config.secrets.SECRETS_PATH is resolved relative to config/secrets.py's own
    # location on disk, NOT the current working directory -- monkeypatch.chdir alone
    # does not isolate it, and a real config/secrets.toml (with a real cohere_api_key)
    # would make this test perform a real, billed network call. Point SECRETS_PATH at
    # a tmp file with only a groq key so get_embedding_provider() genuinely raises
    # ValueError, exercising the real (non-mocked) ingestion path exactly as the page
    # calls it, and proving the failure surfaces via st.error rather than an unhandled
    # exception crashing the page -- without ever touching the network.
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text('groq_api_key = "test-key"\n')
    monkeypatch.setattr(secrets_module, "SECRETS_PATH", secrets_path)

    at = AppTest.from_file(str(DOCUMENTS_PAGE))
    at.run()
    at.text_input(key="documents_title").input("Cell Biology").run()
    at.file_uploader[0].upload("notes.docx", _docx_bytes(["Some content."])).run()
    at.button(key="documents_ingest_button").click().run()

    assert not at.exception
    assert len(at.error) == 1
    assert "Ingestion failed" in at.error[0].value or "unavailable" in at.error[0].value
    assert documents_repo.list_all() == []
