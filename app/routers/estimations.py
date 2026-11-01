"""HTTP routes for software estimation."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.logging_config import get_tracer_logger
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import (
    DEFAULT_PROMPT_VERSION,
    ErrorResponse,
    EstimationRequest,
    EstimationResponse,
    PromptVersion,
)
from app.services.llm_service import generate_estimation

router = APIRouter(tags=["estimations"])
trace = get_tracer_logger()

_ESTIMATE_BODY_EXAMPLE = {
    "description": (
        "Build a B2B SaaS dashboard for inventory alerts with role-based access, "
        "Slack notifications, and CSV export. MVP in about 8 weeks; design is "
        "not ready yet."
    ),
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table",
}


@router.post(
    "/estimate",
    response_model=EstimationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a software estimation",
    description=(
        "Accepts a typed ``EstimationRequest``, renders versioned Jinja2 system "
        "and user prompts, and calls the configured LLM with separate "
        "``system`` / ``user`` roles. Choose the template set with the "
        "``prompt_version`` query parameter (``v1`` or ``v2``). Returns "
        "free-text Markdown plus ``prompt_version``. User input and model "
        "output are logged for traceability."
    ),
    response_description="Free-text estimation plus the prompt template version.",
    responses={
        status.HTTP_200_OK: {
            "description": "Estimation generated successfully.",
            "model": EstimationResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Invalid request body or query (missing fields, invalid enums, "
                "unsupported ``prompt_version``, or ``description`` outside "
                "length bounds)."
            ),
            "model": ErrorResponse,
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Upstream LLM provider failed (auth, network, quota).",
            "model": ErrorResponse,
        },
    },
)
def estimate(
    request: Annotated[
        EstimationRequest,
        Body(
            openapi_examples={
                "inventory_saas": {
                    "summary": "Web SaaS · medium · phases table",
                    "description": (
                        "Sample typed estimation request. Swagger examples are "
                        "documentation only, not live responses."
                    ),
                    "value": _ESTIMATE_BODY_EXAMPLE,
                },
            },
        ),
    ],
    prompt_version: Annotated[
        PromptVersion,
        Query(
            description=(
                "Jinja2 prompt template version under "
                "``app/prompts/estimation/<version>/``. "
                f"Default: ``{DEFAULT_PROMPT_VERSION}``."
            ),
            examples=["v1", "v2"],
        ),
    ] = PromptVersion.V1,
) -> EstimationResponse:
    """Generate a software estimation from a typed request.

    Renders Jinja2 prompts for the requested ``prompt_version``, then calls the
    session-03 LLM wrapper with separate system and user messages.

    :arg request: Validated estimation request.
    :arg prompt_version: Template directory version (``v1`` or ``v2``).
    :return: Free-text estimation and prompt version.
    :raises HTTPException: 502 when prompt render or the LLM provider call fails.
    """
    request_id = str(uuid4())
    version = prompt_version.value
    trace.info(
        "estimate.user_input",
        request_id=request_id,
        endpoint="POST /api/v1/estimate",
        description=request.description,
        description_chars=len(request.description),
        project_type=request.project_type.value,
        detail_level=request.detail_level.value,
        output_format=request.output_format.value,
        prompt_version=version,
    )

    try:
        system, user = render_estimation_prompt(request, version=version)
        result = generate_estimation(system, user)
    except Exception as exc:  # noqa: BLE001 - surface LLM/provider errors as 502
        trace.exception(
            "estimate.model_error",
            request_id=request_id,
            endpoint="POST /api/v1/estimate",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider error: {exc}",
        ) from exc

    response = EstimationResponse(
        text=result.estimation,
        prompt_version=version,
    )

    trace.info(
        "estimate.model_output",
        request_id=request_id,
        endpoint="POST /api/v1/estimate",
        provider=result.provider,
        model=result.model,
        estimation=response.text,
        prompt_version=response.prompt_version,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )

    return response
