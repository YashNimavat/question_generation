import sys
from pathlib import Path

# streamlit only adds the entry script's own directory (app/) to sys.path,
# not the repo root, so first-party packages like `core`/`db`/`services`
# need the repo root added explicitly before they can be imported here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.components.question_card import render_mcq_question
from core.enums import DocumentStatus
from db.repositories import documents_repo, metadata_repo
from services.generation import GenerationError, generate_mcq

st.title("Generate a Question")

topic = st.text_input("Topic", key="generate_topic")
difficulty = st.selectbox(
    "Difficulty", ["easy", "medium", "hard"], key="generate_difficulty"
)

use_rag = st.checkbox("Ground in a document", key="generate_use_rag")
document_id = None
if use_rag:
    ready_documents = [
        doc for doc in documents_repo.list_all() if doc.status == DocumentStatus.READY
    ]
    if not ready_documents:
        st.info("No ingested documents are ready yet. Upload one on the Upload page first.")
    else:
        selected = st.selectbox(
            "Document",
            ready_documents,
            format_func=lambda doc: doc.title,
            key="generate_document",
        )
        document_id = selected.id

if st.button("Generate", key="generate_button"):
    if not topic.strip():
        st.warning("Enter a topic before generating a question.")
    elif use_rag and document_id is None:
        st.warning("Select a document to ground generation in, or turn off the RAG toggle.")
    else:
        try:
            question = generate_mcq(topic=topic, difficulty=difficulty, document_id=document_id)
            st.session_state["last_generated_question"] = question
        except GenerationError as exc:
            st.session_state.pop("last_generated_question", None)
            st.error(f"Generation failed: {exc}")
        except FileNotFoundError:
            st.session_state.pop("last_generated_question", None)
            st.error(
                "No LLM provider configured. Copy config/secrets.example.toml to "
                "config/secrets.toml and add your API key."
            )

question = st.session_state.get("last_generated_question")
if question is not None:
    metadata = None
    if question.generation_metadata_id is not None:
        metadata = metadata_repo.get(question.generation_metadata_id)
    render_mcq_question(question, metadata=metadata)
