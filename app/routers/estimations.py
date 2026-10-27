"""HTTP routes for software estimation."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, status

from app.logging_config import format_trace_message, get_tracer_logger
from app.schemas.estimation import (
    ErrorResponse,
    EstimationRequest,
    EstimationResponse,
)
from app.services.llm_service import generate_estimation

router = APIRouter(tags=["estimations"])
trace = get_tracer_logger()

_ESTIMATE_BODY_EXAMPLE = (
    "In the meeting with the marketing team, the client explained they need a "
    "landing page with a contact form, HubSpot CRM integration, and a blog "
    "section with a WYSIWYG editor. Ideal timeline: 4 weeks. Design already "
    "exists in Figma."
)


@router.post(
    "/estimate",
    response_model=EstimationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a software estimation",
    description=(
        "Accepts a meeting transcription and returns a Markdown software "
        "estimation. Uses **CAG** (Cache-Augmented Generation): static few-shot "
        "examples from `app/context/examples.py` (`CANONICAL_EXAMPLES`) are "
        "injected into the system prompt on every request. No database, "
        "retrieval, or multi-turn memory. "
        "User input and model output are logged for traceability."
    ),
    response_description="Markdown estimation plus model/provider metadata.",
    responses={
        status.HTTP_200_OK: {
            "description": "Estimation generated successfully.",
            "model": EstimationResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Invalid request body (missing `transcription`, or shorter than "
                "the minimum length)."
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
                "landing_hubspot": {
                    "summary": "Landing page + HubSpot + blog",
                    "description": (
                        "Sample meeting transcription long enough for validation. "
                        "Swagger examples are documentation only, not live responses."
                    ),
                    "value": {"transcription": _ESTIMATE_BODY_EXAMPLE},
                },
            },
        ),
    ],
) -> EstimationResponse:
    """Generate a software estimation from a meeting transcription (CAG).

    :arg request: Validated estimation request with the meeting transcription.
    :return: Estimation Markdown and provider metadata.
    :raises HTTPException: 502 when the configured LLM provider call fails.
    """
    request_id = str(uuid4())
    trace.info(
        format_trace_message(
            "estimate.user_input",
            request_id=request_id,
            endpoint="POST /api/v1/estimate",
            transcription=request.transcription,
            transcription_chars=len(request.transcription),
        )
    )

    try:
        result = generate_estimation(request.transcription)
    except Exception as exc:  # noqa: BLE001 - surface LLM/provider errors as 502
        trace.exception(
            format_trace_message(
                "estimate.model_error",
                request_id=request_id,
                endpoint="POST /api/v1/estimate",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider error: {exc}",
        ) from exc

    trace.info(
        format_trace_message(
            "estimate.model_output",
            request_id=request_id,
            endpoint="POST /api/v1/estimate",
            provider=result.provider,
            model=result.model,
            estimation=result.estimation,
            confidence=result.confidence,
            confidence_rationale=result.confidence_rationale,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )
    )

    return EstimationResponse(
        estimation=result.estimation,
        confidence=result.confidence,
        confidence_rationale=result.confidence_rationale,
        model=result.model,
        provider=result.provider,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
