"""Paso 7 integration tests using ``httpx.AsyncClient``."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.schemas.llm import LLMResult
from app.services.attachments import UploadedAttachment
from app.services.sessions import MAX_TURNS, session_store

_TRANSCRIPT = (
    "Build a B2B SaaS dashboard for inventory alerts with Slack notifications "
    "and CSV export for warehouse managers."
)


async def _create_session(client: AsyncClient) -> str:
    """Create a session via the async HTTP client.

    :arg client: ``httpx.AsyncClient`` fixture.
    :return: New ``session_id``.
    :raises AssertionError: If create fails.
    """
    response = await client.post("/api/v1/sessions")
    assert response.status_code == 201
    return response.json()["session_id"]


@pytest.mark.asyncio
async def test_async_session_metadata_updates_across_two_requests(
    async_client: AsyncClient,
) -> None:
    """Link two estimates on one session and assert metadata accumulates.

    :arg async_client: Async HTTPX client.
    :return: None.
    :raises AssertionError: If metadata does not update between turns.
    """
    session_id = await _create_session(async_client)
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

    with patch(
        "app.routers.sessions.LLMService.generate_from_messages",
        side_effect=[first, second],
    ):
        response_one = await async_client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": transcript_one},
        )
        response_two = await async_client.post(
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
    assert session_store.require(session_id).history.turn_count == 2


@pytest.mark.asyncio
async def test_async_pdf_attachment_changes_estimation_output(
    async_client: AsyncClient,
) -> None:
    """Show that adding a PDF attachment changes a concrete output field.

    Qualitative check: without attachments the model stub returns one project
    title; with a PDF Path A upload it returns a different title derived from
    the attachment influence.

    :arg async_client: Async HTTPX client.
    :return: None.
    :raises AssertionError: If outputs do not diverge when a PDF is attached.
    """
    session_id = await _create_session(async_client)

    def _fake_generate(
        self: object,
        messages: list,
        attachments: object = (),
    ) -> LLMResult:
        """Return different titles depending on whether files were attached.

        :arg self: Unused LLMService instance.
        :arg messages: Chat messages prepared for the provider.
        :arg attachments: Path A uploads for the current turn.
        :return: Stub ``LLMResult``.
        :raises: Does not raise under normal operation.
        """
        if attachments:
            return LLMResult(
                estimation="## Estimation: SpecFromPDF\nUses PDF requirements.",
                model="gpt-4o-mini",
                provider="openai",
                prompt_tokens=4,
                completion_tokens=4,
            )
        return LLMResult(
            estimation="## Estimation: TranscriptOnly\nNo PDF context.",
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=2,
            completion_tokens=2,
        )

    def _fake_upload(
        *,
        files: list[tuple[str, bytes, str | None]],
        settings: object,
    ) -> list[UploadedAttachment]:
        """Echo Path A uploads only when the client sent files.

        :arg files: Raw ``(filename, bytes, content_type)`` tuples.
        :arg settings: Unused settings object.
        :return: Provider-ready attachments (empty when no files).
        :raises: Does not raise under normal operation.
        """
        if not files:
            return []
        return [
            UploadedAttachment(
                filename=files[0][0],
                content_type="application/pdf",
                size_bytes=len(files[0][1]),
                file_id="file-pdf-1",
            )
        ]

    with (
        patch("app.routers.sessions.upload_attachments", new=_fake_upload),
        patch(
            "app.routers.sessions.LLMService.generate_from_messages",
            new=_fake_generate,
        ),
    ):
        without_pdf = await async_client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": _TRANSCRIPT},
        )
        with_pdf = await async_client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data={"transcript": _TRANSCRIPT},
            files=[
                (
                    "attachments",
                    ("requirements.pdf", b"%PDF-1.4 demo", "application/pdf"),
                )
            ],
        )

    assert without_pdf.status_code == 200
    assert with_pdf.status_code == 200
    text_without = without_pdf.json()["text"]
    text_with = with_pdf.json()["text"]
    # Concrete output field that changes when the PDF is attached.
    assert "TranscriptOnly" in text_without
    assert "SpecFromPDF" in text_with
    assert text_without != text_with
    assert without_pdf.json()["project_metadata"]["project_name"] == "TranscriptOnly"


@pytest.mark.asyncio
async def test_async_eight_turns_respect_max_turns_window(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Send 8 turns and assert the LLM payload never exceeds ``MAX_TURNS``.

    :arg async_client: Async HTTPX client.
    :arg monkeypatch: Pytest monkeypatch fixture.
    :return: None.
    :raises AssertionError: If prior turns sent to the LLM exceed the window.
    """
    monkeypatch.setenv("SESSION_MAX_TURNS", str(MAX_TURNS))
    get_settings.cache_clear()
    session_id = await _create_session(async_client)
    assert session_store.require(session_id).history.max_turns == MAX_TURNS

    prior_turn_counts: list[int] = []

    def _fake_generate(
        self: object,
        messages: list,
        attachments: object = (),
    ) -> LLMResult:
        """Record how many prior turns are present in the outbound payload.

        :arg self: Unused LLMService instance.
        :arg messages: Chat messages prepared for the provider.
        :arg attachments: Unused Path A uploads.
        :return: Stub ``LLMResult``.
        :raises: Does not raise under normal operation.
        """
        prior_turn_counts.append(len(messages[1:-1]) // 2)
        return LLMResult(
            estimation=f"## Estimation: Window {len(messages)}",
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
            response = await async_client.post(
                f"/api/v1/sessions/{session_id}/estimate",
                data={"transcript": transcript},
            )
            assert response.status_code == 200

    assert session_store.require(session_id).history.turn_count == MAX_TURNS
    assert all(count <= MAX_TURNS for count in prior_turn_counts)
    assert max(prior_turn_counts) == MAX_TURNS
    get_settings.cache_clear()
