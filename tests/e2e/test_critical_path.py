"""Thin e2e checks for critical API journeys (no real LLM calls)."""

from fastapi.testclient import TestClient


def test_docs_and_health_are_reachable(client: TestClient) -> None:
    """Critical path: Swagger UI and health must be available.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If docs or health fail.
    """
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/docs"


def test_estimate_validation_gate_on_critical_path(client: TestClient) -> None:
    """Critical path: invalid estimate payloads are rejected before the LLM.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If validation does not return 422.
    """
    assert client.post("/api/v1/estimate", json={}).status_code == 422
