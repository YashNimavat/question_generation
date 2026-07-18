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

TRUE_FALSE_RUBRIC_V1 = Rubric(
    id="rubric_true_false",
    version="v1",
    question_type=QuestionType.TRUE_FALSE,
    dimensions=[
        RubricDimension(key="correctness", name="Correctness"),
        RubricDimension(key="clarity", name="Clarity"),
        RubricDimension(key="difficulty_calibration", name="Difficulty Calibration"),
        RubricDimension(key="explanation_quality", name="Explanation Quality"),
    ],
)

FILL_BLANK_RUBRIC_V1 = Rubric(
    id="rubric_fill_blank",
    version="v1",
    question_type=QuestionType.FILL_BLANK,
    dimensions=[
        RubricDimension(key="correctness", name="Correctness"),
        RubricDimension(key="clarity", name="Clarity"),
        RubricDimension(key="difficulty_calibration", name="Difficulty Calibration"),
        RubricDimension(key="explanation_quality", name="Explanation Quality"),
        RubricDimension(key="answer_key_completeness", name="Answer Key Completeness"),
    ],
)

_RUBRICS: dict[tuple[QuestionType, str, str], Rubric] = {
    (QuestionType.MCQ, "rubric_mcq", "v1"): MCQ_RUBRIC_V1,
    (QuestionType.TRUE_FALSE, "rubric_true_false", "v1"): TRUE_FALSE_RUBRIC_V1,
    (QuestionType.FILL_BLANK, "rubric_fill_blank", "v1"): FILL_BLANK_RUBRIC_V1,
}

_DEFAULT_RUBRIC_IDS: dict[QuestionType, str] = {
    QuestionType.MCQ: "rubric_mcq",
    QuestionType.TRUE_FALSE: "rubric_true_false",
    QuestionType.FILL_BLANK: "rubric_fill_blank",
}


def get_rubric(
    question_type: QuestionType,
    rubric_id: str | None = None,
    rubric_version: str = "v1",
) -> Rubric:
    rubric_id = rubric_id or _DEFAULT_RUBRIC_IDS.get(question_type, f"rubric_{question_type.value}")
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
