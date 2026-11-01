"""Streamlit form UI for typed software estimations.

Run from the project root (API must be reachable)::

    uv run streamlit run streamlit_app.py

The form builds an ``EstimationRequest`` and ``POST``s it to
``/api/v1/estimate``. Override the API base with ``ESTIMATE_API_BASE_URL``
(default ``http://localhost:8080``; Docker Compose uses ``http://api:8000``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import streamlit as st

from app.schemas.estimation import (
    MAX_DESCRIPTION_LENGTH,
    MIN_DESCRIPTION_LENGTH,
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)

DEFAULT_API_BASE_URL = "http://localhost:8080"


def _api_base_url() -> str:
    """Resolve the FastAPI base URL from the environment.

    :return: Base URL without a trailing slash.
    :raises: Does not raise under normal operation.
    """
    return os.environ.get("ESTIMATE_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


def post_estimation(request: EstimationRequest, *, base_url: str) -> dict[str, object]:
    """POST a typed estimation request to the FastAPI service.

    :arg request: Validated ``EstimationRequest`` payload.
    :arg base_url: FastAPI origin (for example ``http://localhost:8080``).
    :return: Parsed JSON response body.
    :raises urllib.error.HTTPError: When the API returns a non-2xx status.
    :raises urllib.error.URLError: When the API is unreachable.
    :raises json.JSONDecodeError: When the response body is not valid JSON.
    :raises ValueError: When the response JSON is not an object.
    """
    url = f"{base_url}/api/v1/estimate"
    payload = request.model_dump_json().encode("utf-8")
    http_request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(http_request, timeout=120) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("Estimation API returned a non-object JSON payload")
    return parsed


st.set_page_config(
    page_title="Software estimation",
    page_icon=":clipboard:",
    layout="centered",
)

st.title("Software estimation")
st.caption(
    "Fill the form to send a typed ``EstimationRequest`` to the FastAPI service. "
    "The response is free text for now."
)

api_base = _api_base_url()
st.sidebar.header("API")
st.sidebar.code(api_base, language=None)
st.sidebar.caption("Set ``ESTIMATE_API_BASE_URL`` to override.")

with st.form("estimation_form", clear_on_submit=False):
    description = st.text_area(
        "Project description",
        height=180,
        max_chars=MAX_DESCRIPTION_LENGTH,
        placeholder=(
            "Describe the product, integrations, timeline, and constraints "
            f"({MIN_DESCRIPTION_LENGTH}–{MAX_DESCRIPTION_LENGTH} characters)."
        ),
        help=f"{MIN_DESCRIPTION_LENGTH}–{MAX_DESCRIPTION_LENGTH} characters after trim.",
    )
    project_type = st.selectbox(
        "Project type",
        options=list(ProjectType),
        format_func=lambda item: item.value,
        index=list(ProjectType).index(ProjectType.WEB_SAAS),
    )
    detail_level = st.selectbox(
        "Detail level",
        options=list(DetailLevel),
        format_func=lambda item: item.value,
        index=list(DetailLevel).index(DetailLevel.MEDIUM),
    )
    output_format = st.selectbox(
        "Output format",
        options=list(OutputFormat),
        format_func=lambda item: item.value,
        index=list(OutputFormat).index(OutputFormat.PHASES_TABLE),
    )
    submitted = st.form_submit_button("Estimate", type="primary")

if submitted:
    try:
        request = EstimationRequest(
            description=description,
            project_type=project_type,
            detail_level=detail_level,
            output_format=output_format,
        )
    except Exception as exc:  # noqa: BLE001 - show validation errors in the UI
        st.error(f"Invalid form data: {exc}")
    else:
        with st.spinner("Calling estimation API…"):
            try:
                payload = post_estimation(request, base_url=api_base)
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
                prompt_version = payload.get("prompt_version")
                if not isinstance(text, str):
                    st.error("API response missing string field `text`.")
                else:
                    st.success(
                        f"Estimation ready"
                        f"{f' (prompt {prompt_version})' if prompt_version else ''}."
                    )
                    st.markdown(text)
