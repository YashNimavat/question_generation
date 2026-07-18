import json

import pytest

from core.enums import ExperimentStatus, OverallVerdict
from core.models import DimensionScore, ExperimentRun
from db.repositories import evaluations_repo, experiments_repo, metadata_repo, questions_repo
from services.experiment import ExperimentError, aggregate_results, run_experiment
from tests.factories import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    make_embedding_result,
    make_evaluation,
    make_experiment,
    make_judge_scores_json,
    make_llm_result,
    make_mcq_question,
    make_metadata_record,
)

VALID_MCQ_JSON = json.dumps(
    {
        "stem": "What is the capital of France?",
        "options": [
            {"id": "A", "text": "Paris", "is_correct": True},
            {"id": "B", "text": "Lyon", "is_correct": False},
            {"id": "C", "text": "Nice", "is_correct": False},
        ],
        "correct_option_id": "A",
        "explanation": "Paris has been the capital of France since the 10th century.",
    }
)
PASSING_JUDGE_JSON = make_judge_scores_json()


# Every test in this module skips dedup/diversity embedding calls unless it
# explicitly injects a FakeEmbeddingProvider (tests/conftest.py's autouse
# _no_real_secrets fixture leaves no cohere_api_key configured) -- keeps
# happy-path tests focused on generation/evaluation flow without needing to
# queue embedding results too.


def _seed_experiment(db_path, **overrides):
    experiment = make_experiment(**overrides)
    experiments_repo.insert(experiment, db_path=db_path)
    return experiment


def _seed_run(db_path, experiment_id, variant_key, question):
    experiments_repo.insert_run(
        ExperimentRun(
            id=f"{question.id}-run",
            experiment_id=experiment_id,
            variant_key=variant_key,
            question_id=question.id,
            question_version=question.version,
            created_at=question.created_at,
        ),
        db_path=db_path,
    )


def test_run_experiment_requires_at_least_two_variants(db_path):
    with pytest.raises(ExperimentError, match="at least two variants"):
        run_experiment(
            name="n", hypothesis="h", variants=[{"key": "a", "model": "m1"}],
            topic="geography", difficulty="easy", provider=FakeLLMProvider([]), db_path=db_path,
        )
    assert experiments_repo.list_all(db_path=db_path) == []


def test_run_experiment_rejects_duplicate_variant_keys(db_path):
    with pytest.raises(ExperimentError, match="unique"):
        run_experiment(
            name="n", hypothesis="h",
            variants=[{"key": "a", "model": "m1"}, {"key": "a", "model": "m2"}],
            topic="geography", difficulty="easy", provider=FakeLLMProvider([]), db_path=db_path,
        )


def test_run_experiment_rejects_more_than_one_varying_axis(db_path):
    with pytest.raises(ExperimentError, match="Only one axis"):
        run_experiment(
            name="n", hypothesis="h",
            variants=[
                {"key": "a", "model": "m1", "prompt_version": "mcq_v1"},
                {"key": "b", "model": "m2", "prompt_version": "mcq_v2"},
            ],
            topic="geography", difficulty="easy", provider=FakeLLMProvider([]), db_path=db_path,
        )
    assert experiments_repo.list_all(db_path=db_path) == []


def test_run_experiment_model_axis_happy_path(db_path):
    variants = [{"key": "a", "model": "model-a"}, {"key": "b", "model": "model-b"}]
    provider = FakeLLMProvider(
        [
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=PASSING_JUDGE_JSON),
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=PASSING_JUDGE_JSON),
        ]
    )

    experiment = run_experiment(
        name="model comparison",
        hypothesis="model-b produces higher quality",
        variants=variants,
        topic="geography",
        difficulty="easy",
        sample_size=1,
        provider=provider,
        db_path=db_path,
    )

    assert experiment.status == ExperimentStatus.COMPLETE
    runs = experiments_repo.list_runs(experiment.id, db_path=db_path)
    assert sorted(r.variant_key for r in runs) == ["a", "b"]

    # generation calls (index 0, 2) must carry each variant's own model
    assert provider.calls[0]["model"] == "model-a"
    assert provider.calls[2]["model"] == "model-b"


def test_run_experiment_skips_a_failed_sample_without_aborting(db_path):
    variants = [{"key": "a", "model": "model-a"}, {"key": "b", "model": "model-b"}]
    provider = FakeLLMProvider(
        [
            # variant a, sample 1: fails both generation attempts
            make_llm_result(text="not json"),
            make_llm_result(text="still not json"),
            # variant a, sample 2: succeeds
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=PASSING_JUDGE_JSON),
            # variant b, sample 1 and 2: both succeed
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=PASSING_JUDGE_JSON),
            make_llm_result(text=VALID_MCQ_JSON),
            make_llm_result(text=PASSING_JUDGE_JSON),
        ]
    )

    experiment = run_experiment(
        name="n", hypothesis="h", variants=variants, topic="geography", difficulty="easy",
        sample_size=2, provider=provider, db_path=db_path,
    )

    assert experiment.status == ExperimentStatus.COMPLETE
    runs = experiments_repo.list_runs(experiment.id, db_path=db_path)
    by_variant: dict[str, list] = {}
    for run in runs:
        by_variant.setdefault(run.variant_key, []).append(run)
    assert len(by_variant["a"]) == 1  # one of the two samples failed and was skipped
    assert len(by_variant["b"]) == 2


def test_aggregate_results_unknown_experiment_raises(db_path):
    with pytest.raises(ExperimentError):
        aggregate_results("missing-id", db_path=db_path)


def test_aggregate_results_computes_quality_cost_and_latency_per_variant(db_path):
    experiment = _seed_experiment(db_path, variants=[{"key": "a"}, {"key": "b"}])

    def _seed(variant_key, cost, latency, eval_cost, eval_latency, scores, verdict):
        gen_record = metadata_repo.insert(
            make_metadata_record(cost_usd=cost, latency_ms=latency), db_path=db_path
        )
        question = make_mcq_question(generation_metadata_id=gen_record.id)
        questions_repo.insert(question, db_path=db_path)
        eval_record = metadata_repo.insert(
            make_metadata_record(cost_usd=eval_cost, latency_ms=eval_latency), db_path=db_path
        )
        evaluations_repo.insert(
            make_evaluation(
                question, scores=scores, overall_verdict=verdict, evaluation_metadata_id=eval_record.id
            ),
            db_path=db_path,
        )
        _seed_run(db_path, experiment.id, variant_key, question)

    _seed(
        "a", 0.01, 100.0, 0.005, 50.0,
        {"correctness": DimensionScore(score=4, rationale="ok"), "clarity": DimensionScore(score=4, rationale="ok")},
        OverallVerdict.PASS,
    )
    _seed(
        "a", 0.02, 200.0, 0.005, 50.0,
        {"correctness": DimensionScore(score=2, rationale="weak"), "clarity": DimensionScore(score=2, rationale="weak")},
        OverallVerdict.FAIL,
    )
    _seed(
        "b", 0.03, 300.0, 0.01, 100.0,
        {"correctness": DimensionScore(score=4, rationale="ok"), "clarity": DimensionScore(score=3, rationale="ok")},
        OverallVerdict.PASS,
    )

    results = aggregate_results(experiment.id, db_path=db_path)

    a = results["a"]
    assert a.run_count == 2
    assert a.evaluated_count == 2
    assert a.pass_rate == pytest.approx(0.5)
    assert a.avg_scores == {"correctness": pytest.approx(3.0), "clarity": pytest.approx(3.0)}
    assert a.total_cost_usd == pytest.approx(0.01 + 0.005 + 0.02 + 0.005)
    assert a.avg_cost_usd == pytest.approx(a.total_cost_usd / 2)
    assert a.avg_generation_latency_ms == pytest.approx(150.0)
    assert a.avg_evaluation_latency_ms == pytest.approx(50.0)
    assert a.near_duplicate_rate is None  # no embedding provider configured in this test

    b = results["b"]
    assert b.run_count == 1
    assert b.pass_rate == pytest.approx(1.0)
    assert b.avg_scores == {"correctness": pytest.approx(4.0), "clarity": pytest.approx(3.0)}


def test_aggregate_results_near_duplicate_rate_is_not_cross_contaminated_across_variants(db_path):
    experiment = _seed_experiment(db_path, variants=[{"key": "a"}, {"key": "b"}])

    # variant "a": two near-duplicate stems (should raise its near_duplicate_rate).
    # variant "b": one stem that reads similarly to variant a's, but variant b only
    # has one question of its own -- cross-variant similarity must never leak into
    # another variant's rate.
    stems_by_variant = {
        "a": ["Question about Paris one", "Question about Paris two"],
        "b": ["Question about Paris one, but this is variant b's only question"],
    }
    vectors_by_variant = {
        "a": [[1.0, 0.0], [0.99, 0.14]],  # near-duplicate pair, distance well under 0.15
        "b": [[1.0, 0.0]],
    }

    for variant_key, stems in stems_by_variant.items():
        for stem in stems:
            question = make_mcq_question(stem=stem)
            questions_repo.insert(question, db_path=db_path)
            _seed_run(db_path, experiment.id, variant_key, question)

    # variant "b" has only one question, so batch_near_duplicate_rate short-circuits
    # to 0.0 without ever calling embed -- only variant "a" (2 stems) needs a queued
    # embedding result.
    embedding_provider = FakeEmbeddingProvider([make_embedding_result(vectors=vectors_by_variant["a"])])

    results = aggregate_results(experiment.id, embedding_provider=embedding_provider, db_path=db_path)

    assert results["a"].near_duplicate_rate == pytest.approx(1.0)
    # must not be inflated by variant a's stems despite the textual similarity.
    assert results["b"].near_duplicate_rate == pytest.approx(0.0)
