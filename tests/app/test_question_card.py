from app.components.question_card import format_metadata_line
from tests.factories import make_metadata_record


def test_format_metadata_line_includes_provider_model_tokens_latency_cost():
    record = make_metadata_record(
        provider="groq",
        model="llama3-70b",
        input_tokens=120,
        output_tokens=340,
        latency_ms=812.5,
        cost_usd=0.0012,
    )

    line = format_metadata_line(record)

    assert "groq" in line
    assert "llama3-70b" in line
    assert "460 tokens" in line
    assert "812ms" in line
    assert "$0.0012" in line


def test_format_metadata_line_handles_zero_cost_and_tokens():
    record = make_metadata_record(input_tokens=0, output_tokens=0, cost_usd=0.0)

    line = format_metadata_line(record)

    assert "0 tokens" in line
    assert "$0.0000" in line
