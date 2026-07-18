import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from db.repositories import documents_repo
from services.ingestion import IngestionError, ingest_document

st.title("Documents")

st.subheader("Upload a source document")
uploaded_file = st.file_uploader("PDF or Word document", type=["pdf", "doc", "docx"])
title = st.text_input("Title", key="documents_title")
topic = st.text_input("Topic (optional)", key="documents_topic")
tags_input = st.text_input("Tags (comma-separated, optional)", key="documents_tags")

if st.button("Ingest", key="documents_ingest_button"):
    if uploaded_file is None:
        st.warning("Choose a file to upload.")
    elif not title.strip():
        st.warning("Enter a title before ingesting.")
    else:
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        try:
            document = ingest_document(
                file_bytes=uploaded_file.getvalue(),
                filename=uploaded_file.name,
                title=title.strip(),
                topic=topic.strip() or None,
                tags=tags,
            )
            st.session_state["last_ingested_document"] = document
        except IngestionError as exc:
            st.session_state.pop("last_ingested_document", None)
            st.error(f"Ingestion failed: {exc}")

last_document = st.session_state.get("last_ingested_document")
if last_document is not None:
    st.success(
        f"'{last_document.title}' ingested: {last_document.status.value}, "
        f"{last_document.chunk_count} chunks"
    )

st.subheader("Documents")
documents = documents_repo.list_all()
if not documents:
    st.info("No documents ingested yet.")
else:
    st.dataframe(
        [
            {
                "Title": d.title,
                "Filename": d.original_filename,
                "Status": d.status.value,
                "Chunks": d.chunk_count,
                "Topic": d.topic or "",
                "Tags": ", ".join(d.tags),
                "Created": d.created_at,
            }
            for d in documents
        ],
        width="stretch",
    )
