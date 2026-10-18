"""Integration tests for POST /api/v1/estimate."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.schemas.llm import LLMResult


def test_estimate_rejects_missing_body(client: TestClient) -> None:
    """Return 422 when the request body is empty.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status is not 422.
    """
    response = client.post("/api/v1/estimate", json={})
    assert response.status_code == 422


def test_estimate_rejects_short_transcription(client: TestClient) -> None:
    """Return 422 when transcription is below the minimum length.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status is not 422.
    """
    response = client.post("/api/v1/estimate", json={"transcription": "short"})
    assert response.status_code == 422


def test_estimate_returns_estimation_when_llm_succeeds(
    client: TestClient, valid_transcription: str
) -> None:
    """Return 200 with estimation metadata when the LLM service succeeds.

    :arg client: FastAPI test client.
    :arg valid_transcription: Transcription meeting min length.
    :return: None.
    :raises AssertionError: If response shape or status is wrong.
    """
    fake = LLMResult(
        estimation="## Estimation: Test\n\n### Scope\nDemo",
        model="gpt-4o-mini",
        provider="openai",
        confidence=0.81,
        confidence_rationale="Clear requirements in the transcription",
        prompt_tokens=10,
        completion_tokens=20,
    )
    with patch(
        "app.routers.estimations.generate_estimation", return_value=fake
    ):
        response = client.post(
            "/api/v1/estimate",
            json={"transcription": valid_transcription},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["estimation"].startswith("## Estimation:")
    assert payload["confidence"] == 0.81
    assert "Clear requirements" in payload["confidence_rationale"]
    assert payload["model"] == "gpt-4o-mini"
    assert payload["provider"] == "openai"
    assert payload["prompt_tokens"] == 10
    assert payload["completion_tokens"] == 20
    assert "timestamp" in payload


def test_estimate_returns_502_when_llm_fails(
    client: TestClient, valid_transcription: str
) -> None:
    """Return 502 when the LLM provider raises.

    :arg client: FastAPI test client.
    :arg valid_transcription: Transcription meeting min length.
    :return: None.
    :raises AssertionError: If status or detail is wrong.
    """
    with patch(
        "app.routers.estimations.generate_estimation",
        side_effect=RuntimeError("boom"),
    ):
        response = client.post(
            "/api/v1/estimate",
            json={"transcription": valid_transcription},
        )

    assert response.status_code == 502
    assert "LLM provider error" in response.json()["detail"]


def test_openapi_documents_estimate_and_health(client: TestClient) -> None:
    """Publish both API routes in the OpenAPI schema for Swagger.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If required paths are missing.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert "/health" in paths
    assert "/api/v1/estimate" in paths
