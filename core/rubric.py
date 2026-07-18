from pydantic import BaseModel

from core.enums import OverallVerdict, QuestionType
from core.models import DimensionScore


class RubricDimension(BaseModel):
    key: str
    name: str


class Rubric(BaseModel):
    id: str
    version: str
    question_type: QuestionType
    dimensions: list[RubricDimension]

    @property
    def dimension_keys(self) -> set[str]:
        return {d.key for d in self.dimensions}


MCQ_RUBRIC_V1 = Rubric(
    id="rubric_mcq",
    version="v1",
    question_type=QuestionType.MCQ,
    dimensions=[
        RubricDimension(key="correctness", name="Correctness"),
        RubricDimension(key="clarity", name="Clarity"),
        RubricDimension(key="difficulty_calibration", name="Difficulty Calibration"),
        RubricDimension(key="distractor_quality", name="Distractor Quality"),
        RubricDimension(key="explanation_quality", name="Explanation Quality"),
    ],
)

_RUBRICS: dict[tuple[QuestionType, str, str], Rubric] = {
    (QuestionType.MCQ, "rubric_mcq", "v1"): MCQ_RUBRIC_V1,
}


def get_rubric(
    question_type: QuestionType,
    rubric_id: str = "rubric_mcq",
    rubric_version: str = "v1",
) -> Rubric:
    try:
        return _RUBRICS[(question_type, rubric_id, rubric_version)]
    except KeyError:
        raise ValueError(
            f"No rubric registered for type={question_type!r} id={rubric_id!r} "
            f"version={rubric_version!r}"
        ) from None


def compute_overall_verdict(scores: dict[str, DimensionScore]) -> OverallVerdict:
    if scores["correctness"].score < 3:
        return OverallVerdict.FAIL
    if any(s.score == 1 for s in scores.values()):
        return OverallVerdict.FAIL
    if any(s.score == 2 for s in scores.values()):
        return OverallVerdict.NEEDS_REVIEW
    return OverallVerdict.PASS
