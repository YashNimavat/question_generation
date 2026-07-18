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


def test_get_rubric_returns_true_false_rubric():
    rubric = get_rubric(QuestionType.TRUE_FALSE)
    assert rubric.id == "rubric_true_false"
    assert rubric.version == "v1"
    assert rubric.dimension_keys == {
        "correctness",
        "clarity",
        "difficulty_calibration",
        "explanation_quality",
    }


def test_get_rubric_returns_fill_blank_rubric():
    rubric = get_rubric(QuestionType.FILL_BLANK)
    assert rubric.id == "rubric_fill_blank"
    assert rubric.version == "v1"
    assert rubric.dimension_keys == {
        "correctness",
        "clarity",
        "difficulty_calibration",
        "explanation_quality",
        "answer_key_completeness",
    }


def test_get_rubric_unknown_rubric_id_raises():
    with pytest.raises(ValueError):
        get_rubric(QuestionType.MCQ, rubric_id="nonexistent_rubric")


def test_get_rubric_unknown_version_raises():
    with pytest.raises(ValueError):
        get_rubric(QuestionType.MCQ, rubric_version="v99")
