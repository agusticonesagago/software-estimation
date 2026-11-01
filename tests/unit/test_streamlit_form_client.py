"""Unit tests for the Streamlit → API HTTP helper."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)
from streamlit_app import post_estimation


def _sample_request() -> EstimationRequest:
    """Build a valid estimation request for helper tests.

    :return: Typed ``EstimationRequest``.
    :raises: Does not raise under normal operation.
    """
    return EstimationRequest(
        description=(
            "Build a B2B SaaS dashboard for inventory alerts with Slack "
            "notifications and CSV export."
        ),
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
    )


def test_post_estimation_sends_typed_json_and_parses_response() -> None:
    """POST EstimationRequest JSON and return the parsed API body.

    :return: None.
    :raises AssertionError: If URL, headers, body, or parse result are wrong.
    """
    request = _sample_request()
    api_body = {"text": "## Estimation: Demo", "prompt_version": "v1"}
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(api_body).encode("utf-8")
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("streamlit_app.urllib.request.urlopen", return_value=fake_response) as mocked:
        result = post_estimation(request, base_url="http://localhost:8080")

    assert result == api_body
    http_request = mocked.call_args.args[0]
    assert http_request.full_url == "http://localhost:8080/api/v1/estimate"
    assert http_request.get_method() == "POST"
    assert http_request.get_header("Content-type") == "application/json"
    sent = json.loads(http_request.data.decode("utf-8"))
    assert sent["description"] == request.description
    assert sent["project_type"] == "web_saas"
    assert sent["detail_level"] == "medium"
    assert sent["output_format"] == "phases_table"


def test_post_estimation_rejects_non_object_json() -> None:
    """Raise when the API returns a JSON array instead of an object.

    :return: None.
    :raises AssertionError: If ``ValueError`` is not raised.
    """
    fake_response = MagicMock()
    fake_response.read.return_value = b'["not", "an", "object"]'
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("streamlit_app.urllib.request.urlopen", return_value=fake_response):
        with pytest.raises(ValueError, match="non-object"):
            post_estimation(_sample_request(), base_url="http://localhost:8080")
