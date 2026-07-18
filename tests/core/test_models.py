import pytest
from pydantic import TypeAdapter, ValidationError

from core.enums import ReviewDecision
from core.models import (
    FillBlankQuestion,
    McqOption,
    McqPayload,
    McqQuestion,
    Question,
    TrueFalseQuestion,
)
from tests.factories import (
    make_fill_blank_question,
    make_mcq_question,
    make_review,
    make_true_false_question,
)

question_adapter = TypeAdapter(Question)


@pytest.mark.parametrize(
    "factory, expected_cls",
    [
        (make_mcq_question, McqQuestion),
        (make_true_false_question, TrueFalseQuestion),
        (make_fill_blank_question, FillBlankQuestion),
    ],
)
def test_discriminated_union_round_trips(factory, expected_cls):
    question = factory()
    dumped = question.model_dump(mode="json")

    reparsed = question_adapter.validate_python(dumped)

    assert isinstance(reparsed, expected_cls)
    assert reparsed == question


def test_mcq_requires_exactly_one_correct_option():
    with pytest.raises(ValidationError):
        McqPayload(
            options=[
                McqOption(id="a", text="Paris", is_correct=False),
                McqOption(id="b", text="Lyon", is_correct=False),
            ],
            correct_option_id="a",
            explanation="No correct option flagged.",
        )


def test_mcq_rejects_multiple_correct_options():
    with pytest.raises(ValidationError):
        McqPayload(
            options=[
                McqOption(id="a", text="Paris", is_correct=True),
                McqOption(id="b", text="Lyon", is_correct=True),
            ],
            correct_option_id="a",
            explanation="Two correct options flagged.",
        )


def test_mcq_rejects_mismatched_correct_option_id():
    with pytest.raises(ValidationError):
        McqPayload(
            options=[
                McqOption(id="a", text="Paris", is_correct=True),
                McqOption(id="b", text="Lyon", is_correct=False),
            ],
            correct_option_id="b",
            explanation="correct_option_id points at the wrong option.",
        )


def test_review_requires_reason_category_unless_approved():
    question = make_mcq_question()
    with pytest.raises(ValidationError):
        make_review(question, decision=ReviewDecision.REJECT, reason_category=None)


def test_review_approve_does_not_require_reason_category():
    question = make_mcq_question()
    review = make_review(question, decision=ReviewDecision.APPROVE)
    assert review.reason_category is None


def test_review_edit_requires_linked_new_version():
    question = make_mcq_question()
    with pytest.raises(ValidationError):
        make_review(
            question,
            decision=ReviewDecision.EDIT,
            reason_category="formatting_issue",
            linked_new_version=None,
        )


def test_review_non_edit_rejects_linked_new_version():
    question = make_mcq_question()
    with pytest.raises(ValidationError):
        make_review(question, decision=ReviewDecision.APPROVE, linked_new_version=2)
