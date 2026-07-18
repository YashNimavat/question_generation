import streamlit as st

from app.components.question_card import format_metadata_line
from core.enums import OverallVerdict
from core.models import Evaluation
from metadata.models import MetadataRecord

_VERDICT_DISPLAY = {
    OverallVerdict.PASS: ("PASS", "success"),
    OverallVerdict.NEEDS_REVIEW: ("NEEDS REVIEW", "warning"),
    OverallVerdict.FAIL: ("FAIL", "error"),
}


def render_evaluation(
    evaluation: Evaluation, metadata: MetadataRecord | None = None
) -> None:
    label, kind = _VERDICT_DISPLAY[evaluation.overall_verdict]
    getattr(st, kind)(
        f"Verdict: {label} · rubric {evaluation.rubric_id}@{evaluation.rubric_version}"
    )

    for key, dimension in evaluation.scores.items():
        st.write(f"**{key}**: {dimension.score}/4")
        st.caption(dimension.rationale)

    st.caption(f"reference answer used: {evaluation.reference_answer_used}")

    if metadata is not None:
        st.caption(format_metadata_line(metadata))
