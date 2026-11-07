"""Integration tests for session creation."""

from uuid import UUID

from fastapi.testclient import TestClient

from app.services.sessions import session_store


def test_create_session_returns_uuid_and_stores_session(client: TestClient) -> None:
    """POST /api/v1/sessions allocates an in-memory session.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status, body, or store state is unexpected.
    """
    response = client.post("/api/v1/sessions")
    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"session_id"}
    session_id = body["session_id"]
    UUID(session_id)  # raises if not a valid UUID
    stored = session_store.get(session_id)
    assert stored is not None
    assert stored.session_id == session_id
    assert stored.metadata.project_name is None
    assert stored.history.turn_count == 0


def test_create_session_ids_are_unique(client: TestClient) -> None:
    """Each create call returns a distinct session_id.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If ids collide or store size is wrong.
    """
    first = client.post("/api/v1/sessions").json()["session_id"]
    second = client.post("/api/v1/sessions").json()["session_id"]
    assert first != second
    assert len(session_store) == 2
