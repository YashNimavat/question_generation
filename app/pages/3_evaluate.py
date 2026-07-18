import sys
from pathlib import Path

# streamlit only adds the entry script's own directory (app/) to sys.path,
# not the repo root, so first-party packages like `core`/`db`/`services`
# need the repo root added explicitly before they can be imported here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.components.evaluation_card import render_evaluation
from app.components.question_card import render_question
from db.repositories import evaluations_repo, metadata_repo, questions_repo
from services.evaluation import EvaluationError, evaluate

st.title("Evaluate a Question")

questions = questions_repo.list_questions()
if not questions:
    st.info("No questions yet. Generate one first.")
    st.stop()

labels = {
    f"{q.stem[:60]} ({q.type.value}, v{q.version}, {q.status.value})": q for q in questions
}
selected_label = st.selectbox("Question", list(labels.keys()), key="evaluate_question")
question = labels[selected_label]

render_question(question)

reference_answer = st.text_input("Reference answer (optional)", key="evaluate_reference_answer")

if st.button("Run evaluation", key="evaluate_button"):
    try:
        evaluation = evaluate(
            question_id=question.id,
            question_version=question.version,
            reference_answer=reference_answer.strip() or None,
        )
        st.session_state["last_evaluation"] = evaluation
    except EvaluationError as exc:
        st.session_state.pop("last_evaluation", None)
        st.error(f"Evaluation failed: {exc}")
    except FileNotFoundError:
        st.session_state.pop("last_evaluation", None)
        st.error(
            "No LLM provider configured. Copy config/secrets.example.toml to "
            "config/secrets.toml and add your API key."
        )

last_evaluation = st.session_state.get("last_evaluation")
if last_evaluation is not None and last_evaluation.question_id == question.id:
    metadata = metadata_repo.get(last_evaluation.evaluation_metadata_id)
    render_evaluation(last_evaluation, metadata=metadata)

st.subheader("Evaluation history")
history = evaluations_repo.list_for_question(question.id)
if not history:
    st.caption("No evaluations yet for this question lineage.")
for past_evaluation in reversed(history):
    header = (
        f"v{past_evaluation.question_version} · "
        f"{past_evaluation.overall_verdict.value} · {past_evaluation.created_at}"
    )
    with st.expander(header):
        render_evaluation(past_evaluation)
