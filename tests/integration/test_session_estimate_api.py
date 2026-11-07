"""Integration tests for multi-turn session estimate with Path A attachments."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.prompts.loader import render_estimation_prompt
from app.schemas.llm import LLMResult
from app.services.attachments import UploadedAttachment
from app.services.sessions import session_store

_TRANSCRIPT = (
    "Build a B2B SaaS dashboard for inventory alerts with Slack notifications "
    "and CSV export for warehouse managers."
)


def _create_session(client: TestClient) -> str:
    """Create a session and return its id.

    :arg client: FastAPI test client.
    :return: New ``session_id``.
    :raises AssertionError: If create fails.
    """
    response = client.post("/api/v1/sessions")
    assert response.status_code == 201
    return response.json()["session_id"]


def test_session_estimate_unknown_session_returns_404(client: TestClient) -> None:
    """Reject estimates for missing session ids.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status is unexpected.
    """
    response = client.post(
        "/api/v1/sessions/missing/estimate",
        data={"transcript": _TRANSCRIPT},
    )
    assert response.status_code == 404


def test_session_estimate_without_attachments_updates_history(
    client: TestClient,
) -> None:
    """Estimate a turn with transcript only and append to session history.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If response or history is wrong.
    """
    session_id = _create_session(client)
    fake = LLMResult(
        estimation="## Estimation: No files",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=3,
        completion_tokens=5,
    )

    with patch(
        "app.routers.sessions.LLMService.generate_from_messages",
        return_value=fake,
    ) as mock_gen:
        response = client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": _TRANSCRIPT},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "## Estimation: No files"
    assert body["prompt_version"] == "v1"
    assert "project_metadata" in body
    mock_gen.assert_called_once()
    stored = session_store.require(session_id)
    assert stored.history.turn_count == 1
    messages = stored.history.to_messages_list()
    assert messages[-2]["role"] == "user"
    assert messages[-2]["content"] == _TRANSCRIPT
    assert messages[-1]["content"] == "## Estimation: No files"


def test_session_estimate_with_pdf_uses_path_a_upload(client: TestClient) -> None:
    """Upload a PDF via Path A and pass the file_id into generation.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If upload/generate wiring is wrong.
    """
    session_id = _create_session(client)
    uploaded = [
        UploadedAttachment(
            filename="spec.pdf",
            content_type="application/pdf",
            size_bytes=12,
            file_id="file-xyz",
        )
    ]
    fake = LLMResult(
        estimation="## Estimation: With PDF attachment",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=8,
        completion_tokens=6,
    )

    with (
        patch("app.routers.sessions.upload_attachments", return_value=uploaded) as mock_up,
        patch(
            "app.routers.sessions.LLMService.generate_from_messages",
            return_value=fake,
        ) as mock_gen,
    ):
        response = client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": _TRANSCRIPT},
            files=[
                ("attachments", ("spec.pdf", BytesIO(b"%PDF-1.4 demo"), "application/pdf"))
            ],
        )

    assert response.status_code == 200
    assert "With PDF" in response.json()["text"]
    mock_up.assert_called_once()
    mock_gen.assert_called_once()
    assert mock_gen.call_args.kwargs["attachments"] == uploaded
    outbound = mock_gen.call_args.args[0]
    assert outbound[0]["role"] == "system"
    assert outbound[-1]["role"] == "user"


def test_session_estimate_rejects_bad_attachment(client: TestClient) -> None:
    """Return 422 when Path A validation rejects the file type.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status is unexpected.
    """
    session_id = _create_session(client)
    response = client.post(
        f"/api/v1/sessions/{session_id}/estimate",
        data={"transcript": _TRANSCRIPT},
        files=[
            ("attachments", ("virus.exe", BytesIO(b"MZ"), "application/octet-stream"))
        ],
    )
    assert response.status_code == 422


def test_session_estimate_updates_project_metadata_across_turns(
    client: TestClient,
) -> None:
    """Persist heuristic metadata and inject it on the next prompt render.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If metadata does not accumulate between turns.
    """
    session_id = _create_session(client)
    first = LLMResult(
        estimation="## Estimation: Inventory Hub\n\n### Scope\nAlerts MVP.\n",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=1,
        completion_tokens=2,
    )
    second = LLMResult(
        estimation="## Estimation: Inventory Hub\n\nAdd Docker deploy.\n",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=1,
        completion_tokens=2,
    )
    transcript_one = (
        "Build Inventory Hub with React and FastAPI for a team of 3 developers "
        "including Slack alerts."
    )
    transcript_two = (
        "Same Inventory Hub project; also plan Docker packaging for staging."
    )

    with (
        patch(
            "app.routers.sessions.LLMService.generate_from_messages",
            side_effect=[first, second],
        ),
        patch(
            "app.routers.sessions.render_estimation_prompt",
            wraps=render_estimation_prompt,
        ) as mock_render,
    ):
        response_one = client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": transcript_one},
        )
        response_two = client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": transcript_two},
        )

    assert response_one.status_code == 200
    meta_one = response_one.json()["project_metadata"]
    assert meta_one["project_name"] == "Inventory Hub"
    assert meta_one["assumed_team_size"] == 3
    assert "React" in meta_one["mentioned_technologies"]
    assert "FastAPI" in meta_one["mentioned_technologies"]

    assert response_two.status_code == 200
    meta_two = response_two.json()["project_metadata"]
    assert meta_two["project_name"] == "Inventory Hub"
    assert "Docker" in meta_two["mentioned_technologies"]

    # Each turn renders twice (user prompt + system regenerate via history).
    assert mock_render.call_count == 4
    second_turn_renders = mock_render.call_args_list[2:]
    assert any(
        call.kwargs["project_metadata"].project_name == "Inventory Hub"
        and call.kwargs["project_metadata"].assumed_team_size == 3
        for call in second_turn_renders
    )


def test_session_estimate_provider_error_returns_502(client: TestClient) -> None:
    """Map upstream LLM failures to HTTP 502.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status/detail are unexpected.
    """
    session_id = _create_session(client)
    with patch(
        "app.routers.sessions.LLMService.generate_from_messages",
        side_effect=RuntimeError("provider down"),
    ):
        response = client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": _TRANSCRIPT},
        )
    assert response.status_code == 502
    assert "provider down" in response.json()["detail"]


def test_session_estimate_sliding_window_never_exceeds_max_turns(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After more turns than the limit, outbound history stays within the window.

    :arg client: FastAPI test client.
    :arg monkeypatch: Pytest monkeypatch fixture.
    :return: None.
    :raises AssertionError: If the effective window exceeds the limit.
    """
    max_turns = 6
    monkeypatch.setenv("SESSION_MAX_TURNS", str(max_turns))
    get_settings.cache_clear()
    session_id = _create_session(client)
    stored = session_store.require(session_id)
    assert stored.history.max_turns == max_turns

    captured_prior_turn_counts: list[int] = []

    def _fake_generate(self: object, messages: list, attachments: object = ()) -> LLMResult:
        """Capture prior turn counts and return a stub estimation.

        :arg self: Unused LLMService instance.
        :arg messages: Chat messages prepared for the provider.
        :arg attachments: Unused Path A uploads.
        :return: Stub ``LLMResult``.
        :raises: Does not raise under normal operation.
        """
        # messages = system + prior user/assistant pairs + current user
        prior_messages = messages[1:-1]
        captured_prior_turn_counts.append(len(prior_messages) // 2)
        return LLMResult(
            estimation=f"## Estimation: Turn window {len(messages)}",
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=1,
            completion_tokens=1,
        )

    with patch(
        "app.routers.sessions.LLMService.generate_from_messages",
        new=_fake_generate,
    ):
        for index in range(8):
            transcript = (
                f"Continue Inventory Hub estimation turn {index + 1} with React "
                f"and FastAPI details for planning purposes."
            )
            response = client.post(
                f"/api/v1/sessions/{session_id}/estimate",
                data={"transcript": transcript},
            )
            assert response.status_code == 200

    stored = session_store.require(session_id)
    assert stored.history.turn_count == max_turns
    assert all(count <= max_turns for count in captured_prior_turn_counts)
    assert max(captured_prior_turn_counts) == max_turns
    get_settings.cache_clear()
