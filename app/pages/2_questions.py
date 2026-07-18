import sys
from pathlib import Path

# streamlit only adds the entry script's own directory (app/) to sys.path,
# not the repo root, so first-party packages like `core`/`db`/`services`
# need the repo root added explicitly before they can be imported here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.components.question_card import render_question
from core.enums import QuestionStatus, QuestionType
from db.repositories import questions_repo

st.title("Stored Questions")

topic_filter = st.text_input("Topic filter", key="questions_topic_filter")
status_filter = st.selectbox(
    "Status", ["(all)"] + [s.value for s in QuestionStatus], key="questions_status_filter"
)
type_filter = st.selectbox(
    "Type", ["(all)"] + [t.value for t in QuestionType], key="questions_type_filter"
)

status = None if status_filter == "(all)" else QuestionStatus(status_filter)
question_type = None if type_filter == "(all)" else QuestionType(type_filter)

questions = questions_repo.list_questions(
    topic=topic_filter or None, status=status, type=question_type
)

if not questions:
    st.info("No questions found for these filters.")
else:
    for question in questions:
        with st.container(border=True):
            render_question(question)
