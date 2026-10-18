"""Integration tests for estimate I/O trace logging (Loguru)."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from loguru import logger

from app.schemas.llm import LLMResult


def test_estimate_logs_user_input_and_model_output(
    client: TestClient, valid_transcription: str
) -> None:
    """Log transcription input and estimation output with a shared request id.

    :arg client: FastAPI test client.
    :arg valid_transcription: Transcription meeting min length.
    :return: None.
    :raises AssertionError: If expected log events are missing.
    """
    messages: list[str] = []
    sink_id = logger.add(lambda message: messages.append(message.record["message"]))

    fake = LLMResult(
        estimation="## Estimation: Logged\n\n### Scope\nDemo",
        model="gpt-4o-mini",
        provider="openai",
        confidence=0.7,
        confidence_rationale="Logged test",
        prompt_tokens=11,
        completion_tokens=22,
    )
    try:
        with patch(
            "app.routers.estimations.generate_estimation", return_value=fake
        ):
            response = client.post(
                "/api/v1/estimate",
                json={"transcription": valid_transcription},
            )
    finally:
        logger.remove(sink_id)

    assert response.status_code == 200
    text = "\n".join(messages)
    assert "estimate.user_input" in text
    assert "estimate.model_output" in text
    assert valid_transcription in text
    assert "## Estimation: Logged" in text
    assert "provider='openai'" in text
