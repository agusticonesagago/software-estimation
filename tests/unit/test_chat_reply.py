"""Unit tests for Streamlit chat reply formatting."""

from app.schemas.llm import LLMResult
from app.services.chat_reply import (
    format_estimation_reply,
    format_reply_from_raw_payload,
)


def test_format_estimation_reply_includes_body_and_metadata() -> None:
    """Include estimation Markdown plus confidence and model footer.

    :return: None.
    :raises AssertionError: If required fragments are missing.
    """
    result = LLMResult(
        estimation="## Estimation: Demo\n\n| Task | Hours |\n|---|---:|\n| A | 8 |",
        model="gpt-4o-mini",
        provider="openai",
        confidence=0.84,
        confidence_rationale="Clear scope",
        prompt_tokens=100,
        completion_tokens=50,
    )
    text = format_estimation_reply(result)
    assert "## Estimation: Demo" in text
    assert "0.84" in text
    assert "Clear scope" in text
    assert "openai/gpt-4o-mini" in text


def test_format_reply_from_raw_payload_parses_json() -> None:
    """Parse a completed JSON payload into formatted chat Markdown.

    :return: None.
    :raises AssertionError: If parsing or formatting fails.
    """
    raw = (
        '{"estimation":"## Estimation: Stream","confidence":0.7,'
        '"confidence_rationale":"Ok"}'
    )
    text = format_reply_from_raw_payload(
        raw, model="gpt-4o-mini", provider="openai"
    )
    assert "## Estimation: Stream" in text
    assert "0.70" in text


def test_format_reply_from_raw_payload_falls_back_on_invalid_json() -> None:
    """Return raw text when the payload is not valid JSON yet.

    :return: None.
    :raises AssertionError: If fallback is not used.
    """
    raw = '{"estimation": "partial'
    assert format_reply_from_raw_payload(raw, model="m", provider="openai") == raw
