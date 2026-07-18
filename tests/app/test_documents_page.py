from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from streamlit.testing.v1 import AppTest

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
    # tests/conftest.py's autouse _no_real_secrets fixture already points
    # config.secrets.SECRETS_PATH at a groq-only tmp file (real network calls would
    # otherwise be possible here since monkeypatch.chdir alone doesn't isolate it --
    # SECRETS_PATH resolves relative to config/secrets.py's own location on disk, not
    # cwd), so get_embedding_provider() genuinely raises ValueError here, exercising
    # the real (non-mocked) ingestion path exactly as the page calls it and proving
    # the failure surfaces via st.error rather than an unhandled exception crashing
    # the page.
    monkeypatch.chdir(tmp_path)
    init_db("question_intelligence.db")

    at = AppTest.from_file(str(DOCUMENTS_PAGE))
    at.run()
    at.text_input(key="documents_title").input("Cell Biology").run()
    at.file_uploader[0].upload("notes.docx", _docx_bytes(["Some content."])).run()
    at.button(key="documents_ingest_button").click().run()

    assert not at.exception
    assert len(at.error) == 1
    assert "Ingestion failed" in at.error[0].value or "unavailable" in at.error[0].value
    assert documents_repo.list_all() == []
