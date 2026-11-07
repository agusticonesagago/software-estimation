"""Unit tests for the Streamlit → API HTTP helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from streamlit_app import create_session, post_session_estimate


def test_create_session_posts_and_returns_session_id() -> None:
    """POST /sessions and return the new session_id.

    :return: None.
    :raises AssertionError: If URL, method, or parsed id are wrong.
    """
    api_body = {"session_id": "550e8400-e29b-41d4-a716-446655440000"}
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(api_body).encode("utf-8")
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("streamlit_app.urllib.request.urlopen", return_value=fake_response) as mocked:
        session_id = create_session(base_url="http://localhost:8080")

    assert session_id == api_body["session_id"]
    http_request = mocked.call_args.args[0]
    assert http_request.full_url == "http://localhost:8080/api/v1/sessions"
    assert http_request.get_method() == "POST"


def test_create_session_rejects_missing_session_id() -> None:
    """Raise when create-session JSON omits session_id.

    :return: None.
    :raises AssertionError: If ``ValueError`` is not raised.
    """
    fake_response = MagicMock()
    fake_response.read.return_value = b'{"ok": true}'
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("streamlit_app.urllib.request.urlopen", return_value=fake_response):
        with pytest.raises(ValueError, match="session_id"):
            create_session(base_url="http://localhost:8080")


def test_post_session_estimate_sends_multipart_transcript_and_file() -> None:
    """POST multipart transcript + attachment to the session estimate route.

    :return: None.
    :raises AssertionError: If URL, content-type, or body parts are wrong.
    """
    api_body = {
        "text": "## Estimation: Demo",
        "prompt_version": "v1",
        "project_metadata": {
            "project_name": "Demo",
            "assumed_team_size": None,
            "mentioned_technologies": [],
            "agreed_scope": None,
        },
    }
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(api_body).encode("utf-8")
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("streamlit_app.urllib.request.urlopen", return_value=fake_response) as mocked:
        result = post_session_estimate(
            base_url="http://localhost:8080",
            session_id="abc-123",
            transcript="Build a B2B SaaS dashboard for inventory alerts with Slack.",
            attachments=[("spec.pdf", b"%PDF-1.4", "application/pdf")],
        )

    assert result == api_body
    http_request = mocked.call_args.args[0]
    assert http_request.full_url == (
        "http://localhost:8080/api/v1/sessions/abc-123/estimate"
    )
    assert http_request.get_method() == "POST"
    content_type = http_request.get_header("Content-type")
    assert content_type.startswith("multipart/form-data; boundary=")
    body = http_request.data
    assert b'name="transcript"' in body
    assert b"Build a B2B SaaS dashboard" in body
    assert b'filename="spec.pdf"' in body
    assert b"%PDF-1.4" in body


def test_post_session_estimate_rejects_non_object_json() -> None:
    """Raise when the estimate API returns a JSON array.

    :return: None.
    :raises AssertionError: If ``ValueError`` is not raised.
    """
    fake_response = MagicMock()
    fake_response.read.return_value = b'["not", "an", "object"]'
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("streamlit_app.urllib.request.urlopen", return_value=fake_response):
        with pytest.raises(ValueError, match="non-object"):
            post_session_estimate(
                base_url="http://localhost:8080",
                session_id="abc-123",
                transcript="Build a B2B SaaS dashboard for inventory alerts with Slack.",
            )
