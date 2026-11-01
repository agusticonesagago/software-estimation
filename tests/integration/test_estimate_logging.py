"""Integration tests for estimate I/O trace logging (structlog)."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.schemas.llm import LLMResult


def test_estimate_logs_user_input_and_model_output(
    client: TestClient, valid_estimate_payload: dict[str, str]
) -> None:
    """Log description input and estimation output with a shared request id.

    :arg client: FastAPI test client.
    :arg valid_estimate_payload: Typed request body.
    :return: None.
    :raises AssertionError: If expected log events are missing.
    """
    fake = LLMResult(
        estimation="## Estimation: Logged\n\n### Scope\nDemo",
        model="gpt-4o-mini",
        provider="openai",
        confidence=0.7,
        confidence_rationale="Logged test",
        prompt_tokens=11,
        completion_tokens=22,
    )
    with capture_logs() as cap_logs:
        with patch(
            "app.routers.estimations.generate_estimation", return_value=fake
        ):
            response = client.post("/api/v1/estimate", json=valid_estimate_payload)

    assert response.status_code == 200
    events = {entry["event"]: entry for entry in cap_logs}
    assert "estimate.user_input" in events
    assert "estimate.model_output" in events
    assert events["estimate.user_input"]["description"] == valid_estimate_payload[
        "description"
    ]
    assert events["estimate.user_input"]["project_type"] == "web_saas"
    assert events["estimate.model_output"]["estimation"] == "## Estimation: Logged\n\n### Scope\nDemo"
    assert events["estimate.model_output"]["provider"] == "openai"
    assert (
        events["estimate.user_input"]["request_id"]
        == events["estimate.model_output"]["request_id"]
    )
