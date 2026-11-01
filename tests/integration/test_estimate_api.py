"""Integration tests for POST /api/v1/estimate."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.schemas.llm import LLMResult


def test_estimate_rejects_missing_body(client: TestClient) -> None:
    """Return 422 when the request body is empty.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status is not 422.
    """
    response = client.post("/api/v1/estimate", json={})
    assert response.status_code == 422


def test_estimate_rejects_short_description(client: TestClient) -> None:
    """Return 422 when description is below the minimum length.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status is not 422.
    """
    response = client.post(
        "/api/v1/estimate",
        json={
            "description": "short",
            "project_type": "web_saas",
            "detail_level": "medium",
            "output_format": "phases_table",
        },
    )
    assert response.status_code == 422


def test_estimate_rejects_invalid_enum(client: TestClient, valid_description: str) -> None:
    """Return 422 when an enum field has an unknown value.

    :arg client: FastAPI test client.
    :arg valid_description: Description meeting min length.
    :return: None.
    :raises AssertionError: If status is not 422.
    """
    response = client.post(
        "/api/v1/estimate",
        json={
            "description": valid_description,
            "project_type": "desktop_app",
            "detail_level": "medium",
            "output_format": "phases_table",
        },
    )
    assert response.status_code == 422


def test_estimate_returns_text_when_llm_succeeds(
    client: TestClient, valid_estimate_payload: dict[str, str]
) -> None:
    """Return 200 with text and prompt_version when the LLM service succeeds.

    :arg client: FastAPI test client.
    :arg valid_estimate_payload: Typed request body.
    :return: None.
    :raises AssertionError: If response shape or status is wrong.
    """
    fake = LLMResult(
        estimation="## Estimation: Test\n\n### Scope\nDemo",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=10,
        completion_tokens=20,
    )
    with patch(
        "app.routers.estimations.render_estimation_prompt",
        return_value=("SYSTEM_PROMPT", "USER_PROMPT"),
    ) as render_mock, patch(
        "app.routers.estimations.generate_estimation", return_value=fake
    ) as generate_mock:
        response = client.post("/api/v1/estimate", json=valid_estimate_payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"].startswith("## Estimation:")
    assert payload["prompt_version"] == "v1"
    assert set(payload.keys()) == {"text", "prompt_version"}
    render_mock.assert_called_once()
    assert render_mock.call_args.kwargs["version"] == "v1"
    assert (
        render_mock.call_args.args[0].description
        == valid_estimate_payload["description"]
    )
    generate_mock.assert_called_once_with("SYSTEM_PROMPT", "USER_PROMPT")


def test_estimate_accepts_prompt_version_v2_query(
    client: TestClient, valid_estimate_payload: dict[str, str]
) -> None:
    """Honor ``?prompt_version=v2`` when rendering templates.

    :arg client: FastAPI test client.
    :arg valid_estimate_payload: Typed request body.
    :return: None.
    :raises AssertionError: If version is not forwarded or returned.
    """
    fake = LLMResult(
        estimation="## Estimation: V2 path",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=1,
        completion_tokens=2,
    )
    with patch(
        "app.routers.estimations.render_estimation_prompt",
        return_value=("SYSTEM_V2", "USER_V2"),
    ) as render_mock, patch(
        "app.routers.estimations.generate_estimation", return_value=fake
    ) as generate_mock:
        response = client.post(
            "/api/v1/estimate?prompt_version=v2",
            json=valid_estimate_payload,
        )

    assert response.status_code == 200
    assert response.json()["prompt_version"] == "v2"
    assert render_mock.call_args.kwargs["version"] == "v2"
    generate_mock.assert_called_once_with("SYSTEM_V2", "USER_V2")


def test_estimate_rejects_unknown_prompt_version_query(
    client: TestClient, valid_estimate_payload: dict[str, str]
) -> None:
    """Return 422 when ``prompt_version`` is not a supported template version.

    :arg client: FastAPI test client.
    :arg valid_estimate_payload: Typed request body.
    :return: None.
    :raises AssertionError: If status is not 422.
    """
    response = client.post(
        "/api/v1/estimate?prompt_version=v9",
        json=valid_estimate_payload,
    )
    assert response.status_code == 422


def test_estimate_returns_502_when_llm_fails(
    client: TestClient, valid_estimate_payload: dict[str, str]
) -> None:
    """Return 502 when the LLM provider raises.

    :arg client: FastAPI test client.
    :arg valid_estimate_payload: Typed request body.
    :return: None.
    :raises AssertionError: If status or detail is wrong.
    """
    with patch(
        "app.routers.estimations.generate_estimation",
        side_effect=RuntimeError("boom"),
    ):
        response = client.post("/api/v1/estimate", json=valid_estimate_payload)

    assert response.status_code == 502
    assert "LLM provider error" in response.json()["detail"]


def test_openapi_documents_estimate_and_health(client: TestClient) -> None:
    """Publish both API routes in the OpenAPI schema for Swagger.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If required paths are missing.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert "/health" in paths
    assert "/api/v1/estimate" in paths
