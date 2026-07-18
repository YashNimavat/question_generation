import streamlit as st

from core.enums import QuestionType
from core.models import FillBlankQuestion, McqQuestion, Question, TrueFalseQuestion
from metadata.models import MetadataRecord


def format_metadata_line(record: MetadataRecord) -> str:
    total_tokens = record.input_tokens + record.output_tokens
    return (
        f"{record.provider} / {record.model} · {total_tokens} tokens · "
        f"{record.latency_ms:.0f}ms · ${record.cost_usd:.4f}"
    )


def render_question(question: Question, metadata: MetadataRecord | None = None) -> None:
    st.subheader(question.stem)
    st.caption(
        f"type: {question.type.value} · topic: {question.topic} · "
        f"difficulty: {question.difficulty} · status: {question.status.value} · "
        f"version: {question.version}"
    )

    if question.duplicate_of_id is not None:
        message = (
            f"⚠ Similar to existing question {question.duplicate_of_id} "
            f"v{question.duplicate_of_version} (similarity score {question.duplicate_score:.3f})"
        )
        if question.status.value == "rejected":
            st.error(f"{message} — auto-rejected as a duplicate.")
        else:
            st.warning(message)

    _RENDER_PAYLOAD[question.type](question)

    if metadata is not None:
        st.caption(format_metadata_line(metadata))
        if metadata.rag_usage is not None:
            chunk_count = len(metadata.rag_usage.get("chunk_ids", []))
            st.caption(
                f"Grounded in document {metadata.rag_usage.get('document_id')} "
                f"using {chunk_count} chunk(s)."
            )


def _render_mcq_payload(question: McqQuestion) -> None:
    for option in question.payload.options:
        if option.id == question.payload.correct_option_id:
            st.success(f"✓ {option.text}")
        else:
            st.write(f"◯ {option.text}")

    with st.expander("Explanation"):
        st.write(question.payload.explanation)


def _render_true_false_payload(question: TrueFalseQuestion) -> None:
    if question.payload.correct_answer:
        st.success("✓ True")
    else:
        st.error("✗ False")

    with st.expander("Explanation"):
        st.write(question.payload.explanation)


def _render_fill_blank_payload(question: FillBlankQuestion) -> None:
    st.write(f"Blank marker: `{question.payload.blank_marker}`")
    st.write("Accepted answers: " + ", ".join(question.payload.accepted_answers))
    st.caption(f"Case sensitive: {question.payload.case_sensitive}")

    with st.expander("Explanation"):
        st.write(question.payload.explanation)


_RENDER_PAYLOAD = {
    QuestionType.MCQ: _render_mcq_payload,
    QuestionType.TRUE_FALSE: _render_true_false_payload,
    QuestionType.FILL_BLANK: _render_fill_blank_payload,
}
