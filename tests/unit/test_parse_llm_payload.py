"""Unit tests for LLM JSON payload parsing (estimation + confidence)."""

import pytest

from app.schemas.llm import parse_llm_estimation_payload


def test_parse_valid_json_payload() -> None:
    """Parse estimation and confidence from a JSON object.

    :return: None.
    :raises AssertionError: If parsed values are wrong.
    """
    raw = """
    {
      "estimation": "## Estimation: Demo\\n\\n### Scope\\nMVP",
      "confidence": 0.82,
      "confidence_rationale": "Scope is clear"
    }
    """
    payload = parse_llm_estimation_payload(raw)
    assert payload.estimation.startswith("## Estimation:")
    assert payload.confidence == 0.82
    assert payload.confidence_rationale == "Scope is clear"


def test_parse_fenced_json_payload() -> None:
    """Accept JSON wrapped in markdown fences.

    :return: None.
    :raises AssertionError: If fenced JSON is not parsed.
    """
    raw = """```json
{"estimation": "## Ok", "confidence": 0.5, "confidence_rationale": "mid"}
```"""
    payload = parse_llm_estimation_payload(raw)
    assert payload.estimation == "## Ok"
    assert payload.confidence == 0.5
    assert payload.confidence_rationale == "mid"


def test_parse_rejects_confidence_out_of_range() -> None:
    """Reject confidence values outside 0..1.

    :return: None.
    :raises AssertionError: If out-of-range values are accepted.
    """
    with pytest.raises(ValueError, match="confidence"):
        parse_llm_estimation_payload(
            '{"estimation": "## X", "confidence": 1.5, "confidence_rationale": "x"}'
        )


def test_parse_rejects_invalid_json() -> None:
    """Reject non-JSON model output.

    :return: None.
    :raises AssertionError: If invalid JSON is accepted.
    """
    with pytest.raises(ValueError, match="valid JSON"):
        parse_llm_estimation_payload("not json at all")


def test_parse_rejects_non_object_json() -> None:
    """Reject JSON that is not an object.

    :return: None.
    :raises AssertionError: If arrays are accepted.
    """
    with pytest.raises(ValueError, match="object"):
        parse_llm_estimation_payload("[1, 2, 3]")


def test_parse_rejects_blank_estimation() -> None:
    """Reject whitespace-only estimation strings.

    :return: None.
    :raises AssertionError: If blank estimation is accepted.
    """
    with pytest.raises(ValueError):
        parse_llm_estimation_payload(
            '{"estimation": "   ", "confidence": 0.1, "confidence_rationale": "x"}'
        )
