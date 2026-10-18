"""Integration tests for the health endpoint."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """Expose a healthy liveness payload.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status or body is unexpected.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
