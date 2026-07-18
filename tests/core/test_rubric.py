import pytest

from core.enums import OverallVerdict, QuestionType
from core.models import DimensionScore
from core.rubric import compute_overall_verdict, get_rubric


def _scores(**overrides: int) -> dict[str, DimensionScore]:
    base = {
        "correctness": 4,
        "clarity": 4,
        "difficulty_calibration": 4,
        "distractor_quality": 4,
        "explanation_quality": 4,
    }
    base.update(overrides)
    return {k: DimensionScore(score=v, rationale="because") for k, v in base.items()}


def test_all_high_scores_pass():
    assert compute_overall_verdict(_scores()) == OverallVerdict.PASS


def test_low_correctness_fails_even_if_everything_else_is_perfect():
    assert compute_overall_verdict(_scores(correctness=2)) == OverallVerdict.FAIL


def test_non_correctness_dimension_at_one_fails():
    assert compute_overall_verdict(_scores(clarity=1)) == OverallVerdict.FAIL


def test_dimension_at_two_with_no_ones_and_correctness_ok_needs_review():
    assert compute_overall_verdict(_scores(distractor_quality=2)) == OverallVerdict.NEEDS_REVIEW


def test_get_rubric_returns_mcq_rubric():
    rubric = get_rubric(QuestionType.MCQ)
    assert rubric.id == "rubric_mcq"
    assert rubric.version == "v1"
    assert rubric.dimension_keys == {
        "correctness",
        "clarity",
        "difficulty_calibration",
        "distractor_quality",
        "explanation_quality",
    }


def test_get_rubric_unknown_raises():
    with pytest.raises(ValueError):
        get_rubric(QuestionType.TRUE_FALSE)
