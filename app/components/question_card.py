import streamlit as st

from core.models import McqQuestion
from metadata.models import MetadataRecord


def format_metadata_line(record: MetadataRecord) -> str:
    total_tokens = record.input_tokens + record.output_tokens
    return (
        f"{record.provider} / {record.model} · {total_tokens} tokens · "
        f"{record.latency_ms:.0f}ms · ${record.cost_usd:.4f}"
    )


def render_mcq_question(
    question: McqQuestion, metadata: MetadataRecord | None = None
) -> None:
    st.subheader(question.stem)
    st.caption(
        f"topic: {question.topic} · difficulty: {question.difficulty} · "
        f"status: {question.status.value} · version: {question.version}"
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

    for option in question.payload.options:
        if option.id == question.payload.correct_option_id:
            st.success(f"✓ {option.text}")
        else:
            st.write(f"◯ {option.text}")

    with st.expander("Explanation"):
        st.write(question.payload.explanation)

    if metadata is not None:
        st.caption(format_metadata_line(metadata))
        if metadata.rag_usage is not None:
            chunk_count = len(metadata.rag_usage.get("chunk_ids", []))
            st.caption(
                f"Grounded in document {metadata.rag_usage.get('document_id')} "
                f"using {chunk_count} chunk(s)."
            )
