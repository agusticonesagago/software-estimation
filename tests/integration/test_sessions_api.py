"""Integration tests for session creation and debug snapshots."""

from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.schemas.llm import LLMResult
from app.services.sessions import session_store

_TRANSCRIPT = (
    "Build a B2B SaaS dashboard for inventory alerts with Slack notifications "
    "and CSV export for warehouse managers."
)


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


def test_get_session_unknown_returns_404(client: TestClient) -> None:
    """GET unknown session ids as 404.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status is unexpected.
    """
    assert client.get("/api/v1/sessions/missing").status_code == 404


def test_get_session_returns_snapshot_with_last_turn_observed(
    client: TestClient,
) -> None:
    """Expose metadata and the last turn_observed after an estimate.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If snapshot fields are incomplete.
    """
    session_id = client.post("/api/v1/sessions").json()["session_id"]
    empty = client.get(f"/api/v1/sessions/{session_id}")
    assert empty.status_code == 200
    empty_body = empty.json()
    assert empty_body["session_id"] == session_id
    assert empty_body["message_count"] == 0
    assert empty_body["turn_count"] == 0
    assert empty_body["anchors_count"] == 0
    assert empty_body["summary_chars"] == 0
    assert empty_body["last_resolved_tier"] is None
    assert empty_body["last_turn_observed"] is None

    fake = LLMResult(
        estimation="## Estimation: Observed",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=12.5,
        cost_usd=0.000045,
    )
    with patch(
        "app.routers.sessions.LLMService.generate_from_messages",
        return_value=fake,
    ):
        estimate = client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": _TRANSCRIPT},
        )
    assert estimate.status_code == 200

    snapshot = client.get(f"/api/v1/sessions/{session_id}")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["turn_count"] == 1
    assert body["message_count"] >= 3
    observed = body["last_turn_observed"]
    assert observed is not None
    assert observed["turn_index"] == 1
    assert observed["session_id"] == session_id
    assert observed["enriched_transcript_chars"] == len(_TRANSCRIPT)
    assert observed["attachments_total_chars"] == 0
    assert observed["messages_in_window"] == body["message_count"]
    assert observed["anchors_count"] == 0
    assert observed["summary_chars"] == 0
    assert observed["tokens_in"] == 100
    assert observed["tokens_out"] == 50
    assert observed["cost_usd"] == 0.000045
    assert observed["latency_ms"] == 12.5
    assert observed["cache_hit_kind"] == "none"
    assert observed["last_resolved_tier"] is None
