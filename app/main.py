import streamlit as st

st.set_page_config(page_title="Question Intelligence", layout="wide")

st.title("Question Intelligence")
st.write(
    "Generate topic-based questions with an LLM and review what's been stored so far."
)

st.page_link("pages/1_generate.py", label="Generate a question", icon="✨")
st.page_link("pages/2_questions.py", label="Browse stored questions", icon="📋")
st.page_link("pages/3_evaluate.py", label="Evaluate a question", icon="🧪")
st.page_link("pages/4_review.py", label="SME review", icon="✅")
st.page_link("pages/5_documents.py", label="Documents (RAG ingestion)", icon="📄")
st.page_link("pages/6_experiments.py", label="Experiments (compare variants)", icon="🧬")
