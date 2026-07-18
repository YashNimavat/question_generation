import sys
from pathlib import Path

# streamlit only adds the entry script's own directory (app/) to sys.path,
# not the repo root, so first-party packages like `core`/`db`/`services`
# need the repo root added explicitly before they can be imported here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.components.evaluation_card import render_evaluation
from app.components.question_card import render_mcq_question
from core.enums import QuestionStatus, ReasonCategory, ReviewDecision, Severity
from core.models import ReviewFeedback
from db.repositories import evaluations_repo, questions_repo, reviews_repo
from services.review import ReviewError, submit_review

st.title("SME Review")

reviewer_id = st.text_input("Reviewer ID", key="review_reviewer_id")

queue = questions_repo.list_questions(status=QuestionStatus.PENDING_REVIEW)
if not queue:
    st.info("Nothing waiting for review right now.")
    st.stop()

labels = {f"{q.stem[:60]} (v{q.version}, {q.topic})": q for q in queue}
selected_label = st.selectbox("Pending review", list(labels.keys()), key="review_question_select")
question = labels[selected_label]

render_mcq_question(question)

evaluations = evaluations_repo.list_for_question(question.id)
if evaluations:
    st.caption("Latest auto-evaluation")
    render_evaluation(evaluations[-1])

decision = st.radio(
    "Decision",
    [ReviewDecision.APPROVE, ReviewDecision.REJECT, ReviewDecision.EDIT],
    format_func=lambda d: d.value,
    key="review_decision",
)

reason_category = None
comment = None
severity = None
if decision != ReviewDecision.APPROVE:
    reason_category = st.selectbox(
        "Reason category", list(ReasonCategory), format_func=lambda r: r.value, key="review_reason"
    )
    comment = st.text_area("Comment", key="review_comment")
    severity = st.selectbox(
        "Severity", [None, *Severity], format_func=lambda s: s.value if s else "(none)", key="review_severity"
    )

edited_payload = None
if decision == ReviewDecision.EDIT:
    st.subheader("Edit MCQ")
    option_texts = {}
    for option in question.payload.options:
        option_texts[option.id] = st.text_input(
            f"Option {option.id}", value=option.text, key=f"review_edit_option_{option.id}"
        )
    correct_option_id = st.radio(
        "Correct option",
        [o.id for o in question.payload.options],
        index=[o.id for o in question.payload.options].index(question.payload.correct_option_id),
        key="review_edit_correct_option",
    )
    explanation = st.text_area(
        "Explanation", value=question.payload.explanation, key="review_edit_explanation"
    )
    edited_payload = {
        "options": [
            {"id": opt_id, "text": text, "is_correct": opt_id == correct_option_id}
            for opt_id, text in option_texts.items()
        ],
        "correct_option_id": correct_option_id,
        "explanation": explanation,
    }

if st.button("Submit review", key="review_submit_button"):
    if not reviewer_id.strip():
        st.warning("Enter a reviewer ID before submitting.")
    else:
        try:
            review = submit_review(
                question_id=question.id,
                question_version=question.version,
                reviewer_id=reviewer_id.strip(),
                decision=decision,
                feedback=ReviewFeedback(
                    reason_category=reason_category,
                    comment=comment.strip() if comment else None,
                    severity=severity,
                ),
                edited_payload=edited_payload,
            )
            st.session_state["last_review"] = review
        except ReviewError as exc:
            st.session_state.pop("last_review", None)
            st.error(f"Review failed: {exc}")

last_review = st.session_state.get("last_review")
if last_review is not None and last_review.question_id == question.id:
    st.success(f"Recorded {last_review.decision.value} by {last_review.reviewer_id}")
    if last_review.linked_new_version is not None:
        st.caption(f"Edit created version {last_review.linked_new_version}")

st.subheader("Review history")
history = reviews_repo.list_for_question(question.id)
if not history:
    st.caption("No reviews yet for this question lineage.")
for past_review in reversed(history):
    header = f"v{past_review.question_version} · {past_review.decision.value} · {past_review.created_at}"
    with st.expander(header):
        st.write(f"Reviewer: {past_review.reviewer_id}")
        if past_review.reason_category:
            st.write(f"Reason: {past_review.reason_category.value}")
        if past_review.comment:
            st.write(past_review.comment)
        if past_review.severity:
            st.caption(f"Severity: {past_review.severity.value}")
        if past_review.linked_new_version:
            st.caption(f"Linked new version: {past_review.linked_new_version}")
