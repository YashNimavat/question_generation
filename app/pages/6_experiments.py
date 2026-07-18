import sys
from pathlib import Path

# streamlit only adds the entry script's own directory (app/) to sys.path, not the
# repo root, so first-party packages like `core`/`db`/`services` need the repo root
# added explicitly before they can be imported here.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from core.enums import DocumentStatus
from db.repositories import documents_repo, experiments_repo
from services import generation
from services.experiment import ExperimentError, VariantMetrics, aggregate_results, run_experiment

st.title("Experiments")
st.caption(
    "Run the same generation task across two variants that differ on exactly one "
    "axis, then compare quality, cost, latency, and diversity."
)

AXIS_LABELS = {"Model": "model", "Prompt version": "prompt_version", "RAG on/off": "document_id"}

st.header("New experiment")

name = st.text_input("Name", key="experiment_name")
hypothesis = st.text_input("Hypothesis", key="experiment_hypothesis")
topic = st.text_input("Topic", key="experiment_topic")
difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"], key="experiment_difficulty")
sample_size = st.number_input(
    "Samples per variant", min_value=1, max_value=10, value=3, key="experiment_sample_size"
)
axis_label = st.radio("Axis to compare", list(AXIS_LABELS.keys()), key="experiment_axis")
axis = AXIS_LABELS[axis_label]

variant_a: dict = {"key": "a"}
variant_b: dict = {"key": "b"}

if axis == "model":
    variant_a["model"] = st.text_input(
        "Variant A model", value="llama-3.3-70b-versatile", key="experiment_model_a"
    )
    variant_b["model"] = st.text_input(
        "Variant B model", value="llama-3.1-8b-instant", key="experiment_model_b"
    )
elif axis == "prompt_version":
    prompt_versions = list(generation.PROMPT_VERSIONS.keys())
    variant_a["prompt_version"] = st.selectbox(
        "Variant A prompt version", prompt_versions, index=0, key="experiment_prompt_a"
    )
    variant_b["prompt_version"] = st.selectbox(
        "Variant B prompt version", prompt_versions, index=min(1, len(prompt_versions) - 1),
        key="experiment_prompt_b",
    )
else:  # RAG on/off
    variant_a["document_id"] = None
    ready_documents = [
        doc for doc in documents_repo.list_all() if doc.status == DocumentStatus.READY
    ]
    if not ready_documents:
        st.info("No ingested documents are ready yet. Upload one on the Documents page first.")
        variant_b["document_id"] = None
    else:
        selected = st.selectbox(
            "Variant B document",
            ready_documents,
            format_func=lambda doc: doc.title,
            key="experiment_document_b",
        )
        variant_b["document_id"] = selected.id

if st.button("Run experiment", key="run_experiment_button"):
    if not name.strip() or not hypothesis.strip() or not topic.strip():
        st.warning("Name, hypothesis, and topic are all required.")
    elif axis == "document_id" and variant_b.get("document_id") is None:
        st.warning("Select a document for variant B, or choose a different axis.")
    else:
        try:
            experiment = run_experiment(
                name=name,
                hypothesis=hypothesis,
                variants=[variant_a, variant_b],
                topic=topic,
                difficulty=difficulty,
                sample_size=int(sample_size),
            )
            st.session_state["last_experiment_id"] = experiment.id
        except ExperimentError as exc:
            st.error(f"Experiment failed: {exc}")
        except FileNotFoundError:
            st.error(
                "No LLM provider configured. Copy config/secrets.example.toml to "
                "config/secrets.toml and add your API key."
            )


def _render_comparison(experiment_id: str) -> None:
    experiment = experiments_repo.get(experiment_id)
    if experiment is None:
        st.error("Experiment not found.")
        return

    st.subheader(experiment.name)
    st.caption(f"{experiment.hypothesis} -- status: {experiment.status.value}")

    try:
        results = aggregate_results(experiment_id)
    except ExperimentError as exc:
        st.error(f"Could not compute results: {exc}")
        return

    columns = st.columns(len(results))
    for column, (variant_key, metrics) in zip(columns, results.items()):
        variant = next(v for v in experiment.variants if v["key"] == variant_key)
        with column:
            st.markdown(f"**Variant {variant_key}**")
            st.caption(", ".join(f"{k}={v}" for k, v in variant.items() if k != "key" and v is not None))
            _render_variant_metrics(metrics)


def _render_variant_metrics(metrics: VariantMetrics) -> None:
    st.metric("Questions generated", metrics.run_count)
    st.metric(
        "Pass rate",
        "n/a" if metrics.pass_rate is None else f"{metrics.pass_rate:.0%}",
    )
    st.metric(
        "Near-duplicate rate",
        "n/a" if metrics.near_duplicate_rate is None else f"{metrics.near_duplicate_rate:.0%}",
    )
    st.metric("Avg cost/question", f"${metrics.avg_cost_usd:.4f}")
    st.metric("Total cost", f"${metrics.total_cost_usd:.4f}")
    if metrics.avg_generation_latency_ms is not None:
        st.metric("Avg generation latency", f"{metrics.avg_generation_latency_ms:.0f}ms")
    if metrics.avg_scores:
        st.caption("Avg rubric scores:")
        st.bar_chart(metrics.avg_scores)


last_experiment_id = st.session_state.get("last_experiment_id")
if last_experiment_id is not None:
    st.header("Results")
    _render_comparison(last_experiment_id)

st.header("Past experiments")
past_experiments = experiments_repo.list_all()
if not past_experiments:
    st.caption("No experiments yet.")
else:
    labels = {f"{e.name} ({e.created_at})": e for e in past_experiments}
    selected_label = st.selectbox("View a past experiment", list(labels.keys()), key="past_experiment_select")
    if st.button("Show comparison", key="show_past_experiment_button"):
        st.session_state["last_experiment_id"] = labels[selected_label].id
        st.rerun()
