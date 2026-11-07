"""Streamlit multi-turn estimation client (session + attachments).

Run from the project root (API must be reachable)::

    uv run streamlit run streamlit_app.py

On load the app calls ``POST /api/v1/sessions`` and stores ``session_id`` in
``st.session_state``. Each estimate is ``multipart/form-data`` to
``POST /api/v1/sessions/{session_id}/estimate``. Override the API base with
``ESTIMATE_API_BASE_URL`` (default ``http://localhost:8080``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4

import streamlit as st

_DEFAULT_API_BASE_URL = "http://localhost:8080"
_MIN_TRANSCRIPT_LENGTH = 20
_MAX_TRANSCRIPT_LENGTH = 2000
_EMPTY_METADATA: dict[str, Any] = {
    "project_name": None,
    "assumed_team_size": None,
    "mentioned_technologies": [],
    "agreed_scope": None,
}


def _api_base_url() -> str:
    """Resolve the FastAPI base URL from the environment.

    :return: Base URL without a trailing slash.
    :raises: Does not raise under normal operation.
    """
    return os.environ.get("ESTIMATE_API_BASE_URL", _DEFAULT_API_BASE_URL).rstrip("/")


def _parse_json_object(body: str) -> dict[str, Any]:
    """Parse a JSON object from an HTTP response body.

    :arg body: Raw response text.
    :return: Parsed JSON object.
    :raises json.JSONDecodeError: When the body is not valid JSON.
    :raises ValueError: When the JSON value is not an object.
    """
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("API returned a non-object JSON payload")
    return parsed


def create_session(*, base_url: str) -> str:
    """Create an in-memory estimation session and return its id.

    :arg base_url: FastAPI origin (for example ``http://localhost:8080``).
    :return: New ``session_id`` UUID string.
    :raises urllib.error.HTTPError: When the API returns a non-2xx status.
    :raises urllib.error.URLError: When the API is unreachable.
    :raises json.JSONDecodeError: When the response body is not valid JSON.
    :raises ValueError: When ``session_id`` is missing from the response.
    """
    url = f"{base_url}/api/v1/sessions"
    http_request = urllib.request.Request(
        url,
        data=b"",
        headers={"Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(http_request, timeout=30) as response:
        body = response.read().decode("utf-8")
    payload = _parse_json_object(body)
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("Create-session response missing string field `session_id`")
    return session_id


def _encode_multipart(
    fields: list[tuple[str, str]],
    files: list[tuple[str, str, bytes, str]],
) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for transcript + attachments.

    :arg fields: Form fields as ``(name, value)`` pairs.
    :arg files: Uploads as ``(field_name, filename, content, content_type)``.
    :return: ``(body_bytes, content_type_header)``.
    :raises: Does not raise under normal operation.
    """
    boundary = f"----streamlitboundary{uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields:
        lines.append(f"--{boundary}".encode("ascii"))
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(value.encode("utf-8"))
    for field_name, filename, content, content_type in files:
        safe_name = filename.replace('"', "_")
        lines.append(f"--{boundary}".encode("ascii"))
        lines.append(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{safe_name}"'
            ).encode("utf-8")
        )
        lines.append(f"Content-Type: {content_type}".encode("utf-8"))
        lines.append(b"")
        lines.append(content)
    lines.append(f"--{boundary}--".encode("ascii"))
    lines.append(b"")
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


def post_session_estimate(
    *,
    base_url: str,
    session_id: str,
    transcript: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> dict[str, Any]:
    """POST a multi-turn estimate with optional Path A attachments.

    :arg base_url: FastAPI origin.
    :arg session_id: Session UUID from ``create_session``.
    :arg transcript: User transcript for this turn.
    :arg attachments: Optional ``(filename, bytes, content_type)`` uploads.
    :return: Parsed JSON response (``text``, ``prompt_version``, ``project_metadata``).
    :raises urllib.error.HTTPError: When the API returns a non-2xx status.
    :raises urllib.error.URLError: When the API is unreachable.
    :raises json.JSONDecodeError: When the response body is not valid JSON.
    :raises ValueError: When the response JSON is not an object.
    """
    url = f"{base_url}/api/v1/sessions/{session_id}/estimate"
    file_parts: list[tuple[str, str, bytes, str]] = []
    for filename, content, content_type in attachments or []:
        file_parts.append(("attachments", filename, content, content_type))
    body, content_type = _encode_multipart(
        [("transcript", transcript)],
        file_parts,
    )
    http_request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": content_type, "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(http_request, timeout=180) as response:
        raw = response.read().decode("utf-8")
    return _parse_json_object(raw)


def _ensure_session(base_url: str) -> None:
    """Create a session on first load if ``session_id`` is missing.

    :arg base_url: FastAPI origin.
    :return: None.
    :raises: Does not raise; stores errors in ``st.session_state``.
    """
    if st.session_state.get("session_id"):
        return
    try:
        st.session_state.session_id = create_session(base_url=base_url)
        st.session_state.project_metadata = dict(_EMPTY_METADATA)
        st.session_state.turns = []
        st.session_state.session_error = None
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        st.session_state.session_id = None
        st.session_state.session_error = str(exc)


def _reset_conversation(base_url: str) -> None:
    """Start a new API session and clear local turn / metadata state.

    :arg base_url: FastAPI origin.
    :return: None.
    :raises: Does not raise; stores errors in ``st.session_state``.
    """
    try:
        st.session_state.session_id = create_session(base_url=base_url)
        st.session_state.project_metadata = dict(_EMPTY_METADATA)
        st.session_state.turns = []
        st.session_state.session_error = None
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        st.session_state.session_error = str(exc)


def _render_metadata_panel(metadata: dict[str, Any]) -> None:
    """Show durable project memory separately from chat history.

    :arg metadata: ``project_metadata`` dict from the API.
    :return: None.
    :raises: Does not raise under normal operation.
    """
    st.subheader("Project metadata (memory)")
    st.caption(
        "Durable facts kept outside the sliding chat history. "
        "Empty on the first turn; updated after each estimate."
    )
    st.json(metadata)


st.set_page_config(
    page_title="Software estimation (session)",
    page_icon=":clipboard:",
    layout="wide",
)

api_base = _api_base_url()
_ensure_session(api_base)

st.title("Software estimation — multi-turn session")
st.caption(
    "Creates a ``session_id`` on load, sends transcript + optional attachments "
    "to ``POST /api/v1/sessions/{session_id}/estimate``, and shows "
    "``project_metadata`` separately from the turn history."
)

with st.sidebar:
    st.header("API")
    st.code(api_base, language=None)
    st.caption("Set ``ESTIMATE_API_BASE_URL`` to override.")
    st.divider()
    st.header("Session")
    if st.session_state.get("session_error"):
        st.error(st.session_state.session_error)
    session_id = st.session_state.get("session_id")
    if session_id:
        st.code(session_id, language=None)
    else:
        st.warning("No active session. Check that the API is running.")
    if st.button("Nueva conversación", type="secondary", use_container_width=True):
        _reset_conversation(api_base)
        st.rerun()
    st.divider()
    _render_metadata_panel(st.session_state.get("project_metadata") or dict(_EMPTY_METADATA))

col_form, col_history = st.columns((1, 1), gap="large")

with col_form:
    st.subheader("New turn")
    transcript = st.text_area(
        "Transcript",
        height=220,
        max_chars=_MAX_TRANSCRIPT_LENGTH,
        placeholder=(
            f"Paste the meeting / project transcript "
            f"({_MIN_TRANSCRIPT_LENGTH}–{_MAX_TRANSCRIPT_LENGTH} characters)."
        ),
        help=f"{_MIN_TRANSCRIPT_LENGTH}–{_MAX_TRANSCRIPT_LENGTH} characters.",
        key="transcript_input",
    )
    uploads = st.file_uploader(
        "Attachments (optional, Path A)",
        type=["pdf", "docx", "doc", "txt", "md", "pptx", "xlsx"],
        accept_multiple_files=True,
        help="Uploaded to the provider Files / multimodal path — not extracted locally.",
    )
    estimate_clicked = st.button(
        "Estimate",
        type="primary",
        disabled=not bool(session_id),
    )

    if estimate_clicked and session_id:
        cleaned = (transcript or "").strip()
        if len(cleaned) < _MIN_TRANSCRIPT_LENGTH:
            st.error(
                f"Transcript must be at least {_MIN_TRANSCRIPT_LENGTH} characters."
            )
        else:
            attachment_payload: list[tuple[str, bytes, str]] = []
            for upload in uploads or []:
                attachment_payload.append(
                    (
                        upload.name,
                        upload.getvalue(),
                        upload.type or "application/octet-stream",
                    )
                )
            with st.spinner("Calling session estimate API…"):
                try:
                    payload = post_session_estimate(
                        base_url=api_base,
                        session_id=session_id,
                        transcript=cleaned,
                        attachments=attachment_payload,
                    )
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")
                    st.error(f"API error {exc.code}: {detail}")
                except urllib.error.URLError as exc:
                    st.error(
                        f"Cannot reach API at {api_base}. "
                        f"Is the service running? ({exc.reason})"
                    )
                except (json.JSONDecodeError, ValueError) as exc:
                    st.error(f"Unexpected API response: {exc}")
                else:
                    text = payload.get("text")
                    metadata = payload.get("project_metadata")
                    if not isinstance(text, str):
                        st.error("API response missing string field `text`.")
                    else:
                        if isinstance(metadata, dict):
                            st.session_state.project_metadata = metadata
                        turns = list(st.session_state.get("turns") or [])
                        turns.append(
                            {
                                "transcript": cleaned,
                                "estimation": text,
                                "prompt_version": payload.get("prompt_version"),
                                "attachments": [item[0] for item in attachment_payload],
                            }
                        )
                        st.session_state.turns = turns
                        version = payload.get("prompt_version")
                        suffix = f" (prompt {version})" if version else ""
                        st.success(f"Estimation ready{suffix}.")
                        st.rerun()

with col_history:
    st.subheader("Turn history (chat window)")
    st.caption(
        "Local view of user/assistant turns in this browser session. "
        "The API also keeps a sliding window server-side (see ``SESSION_MAX_TURNS``)."
    )
    turns = st.session_state.get("turns") or []
    if not turns:
        st.info("No turns yet. Submit a transcript to start the conversation.")
    else:
        for index, turn in enumerate(reversed(turns), start=1):
            turn_number = len(turns) - index + 1
            with st.expander(
                f"Turn {turn_number}"
                + (
                    f" · {', '.join(turn['attachments'])}"
                    if turn.get("attachments")
                    else ""
                ),
                expanded=(index == 1),
            ):
                st.markdown("**Transcript**")
                st.write(turn["transcript"])
                st.markdown("**Estimation**")
                st.markdown(turn["estimation"])
