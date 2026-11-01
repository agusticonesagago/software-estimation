"""Unit tests for typed estimation request validation."""

import pytest
from pydantic import ValidationError

from app.schemas.estimation import (
    MAX_DESCRIPTION_LENGTH,
    MIN_DESCRIPTION_LENGTH,
    DetailLevel,
    EstimationRequest,
    EstimationResponse,
    OutputFormat,
    ProjectType,
    ReferenceProject,
)

_VALID_DESCRIPTION = (
    "Build a B2B SaaS dashboard for inventory alerts with Slack notifications."
)


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    """Build a valid EstimationRequest kwargs dict.

    :arg overrides: Fields to replace in the default payload.
    :return: Keyword arguments for ``EstimationRequest``.
    :raises: Does not raise under normal operation.
    """
    payload: dict[str, object] = {
        "description": _VALID_DESCRIPTION,
        "project_type": ProjectType.WEB_SAAS,
        "detail_level": DetailLevel.MEDIUM,
        "output_format": OutputFormat.PHASES_TABLE,
    }
    payload.update(overrides)
    return payload


def test_estimation_request_accepts_valid_payload() -> None:
    """Accept a fully typed estimation request.

    :return: None.
    :raises AssertionError: If validation unexpectedly fails.
    """
    request = EstimationRequest(**_valid_kwargs())
    assert request.description == _VALID_DESCRIPTION
    assert request.project_type is ProjectType.WEB_SAAS
    assert request.detail_level is DetailLevel.MEDIUM
    assert request.output_format is OutputFormat.PHASES_TABLE


def test_description_strips_whitespace() -> None:
    """Strip leading and trailing whitespace on description.

    :return: None.
    :raises AssertionError: If stripping does not occur.
    """
    request = EstimationRequest(**_valid_kwargs(description=f"  {_VALID_DESCRIPTION}  "))
    assert request.description == _VALID_DESCRIPTION


def test_description_rejects_too_short() -> None:
    """Reject descriptions shorter than the minimum length.

    :return: None.
    :raises AssertionError: If a short value is accepted.
    """
    with pytest.raises(ValidationError):
        EstimationRequest(**_valid_kwargs(description="too short"))


def test_description_rejects_too_long() -> None:
    """Reject descriptions longer than the maximum length.

    :return: None.
    :raises AssertionError: If an oversized value is accepted.
    """
    with pytest.raises(ValidationError):
        EstimationRequest(
            **_valid_kwargs(description="x" * (MAX_DESCRIPTION_LENGTH + 1))
        )


def test_description_rejects_whitespace_only_padding() -> None:
    """Reject values that only reach min_length via surrounding spaces.

    :return: None.
    :raises AssertionError: If padded whitespace passes validation.
    """
    padded = (" " * 10) + ("z" * (MIN_DESCRIPTION_LENGTH - 5)) + (" " * 10)
    assert len(padded) >= MIN_DESCRIPTION_LENGTH
    assert len(padded.strip()) < MIN_DESCRIPTION_LENGTH
    with pytest.raises(ValidationError):
        EstimationRequest(**_valid_kwargs(description=padded))


def test_enums_reject_invalid_values() -> None:
    """Reject unknown enum strings for typed fields.

    :return: None.
    :raises AssertionError: If an invalid enum is accepted.
    """
    with pytest.raises(ValidationError):
        EstimationRequest(**_valid_kwargs(project_type="desktop_app"))
    with pytest.raises(ValidationError):
        EstimationRequest(**_valid_kwargs(detail_level="extreme"))
    with pytest.raises(ValidationError):
        EstimationRequest(**_valid_kwargs(output_format="pdf"))


def test_estimation_request_accepts_optional_reference_projects() -> None:
    """Accept an optional list of similar past projects.

    :return: None.
    :raises AssertionError: If references are dropped or rejected.
    """
    request = EstimationRequest(
        **_valid_kwargs(
            reference_projects=[
                {
                    "name": "Warehouse alerts MVP",
                    "summary": "React + Slack alerts in 4 weeks.",
                    "actual_hours": 96,
                }
            ]
        )
    )
    assert request.reference_projects is not None
    assert len(request.reference_projects) == 1
    assert request.reference_projects[0].name == "Warehouse alerts MVP"
    assert request.reference_projects[0].actual_hours == 96

    without = EstimationRequest(**_valid_kwargs())
    assert without.reference_projects is None


def test_estimation_response_requires_text_and_prompt_version() -> None:
    """Require free-text output and prompt version on the response.

    :return: None.
    :raises AssertionError: If the response shape is wrong.
    """
    response = EstimationResponse(text="## Estimation", prompt_version="v1")
    assert response.text == "## Estimation"
    assert response.prompt_version == "v1"
    with pytest.raises(ValidationError):
        EstimationResponse(text="only text")  # type: ignore[call-arg]
