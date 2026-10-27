"""Pydantic request/response models exposed in OpenAPI."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_TRANSCRIPTION_LENGTH = 100

ExampleFormat = Literal["markdown", "json", "narrative"]


class EstimationRequest(BaseModel):
    """Payload for generating a software estimation from a meeting transcription."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "transcription": (
                        "In the meeting with the marketing team, the client explained "
                        "they need a landing page with a contact form, HubSpot CRM "
                        "integration, and a blog section with a WYSIWYG editor. "
                        "Ideal timeline: 4 weeks. Design already exists in Figma."
                    )
                }
            ]
        }
    )

    transcription: str = Field(
        ...,
        min_length=MIN_TRANSCRIPTION_LENGTH,
        description=(
            "Raw meeting transcription to turn into a software estimation. "
            f"Must be at least {MIN_TRANSCRIPTION_LENGTH} characters after trimming "
            "whitespace; shorter values return HTTP 422."
        ),
        examples=[
            "Client needs a landing page with contact form and HubSpot integration "
            "in 4 weeks. Design is ready in Figma. Scope includes SEO basics and "
            "a small blog section with a WYSIWYG editor."
        ],
    )

    @field_validator("transcription")
    @classmethod
    def transcription_must_meet_minimum_length(cls, value: str) -> str:
        """Reject blank or too-short transcriptions after trimming.

        :arg value: Raw transcription from the request body.
        :return: Stripped transcription when it meets the minimum length.
        :raises ValueError: If the stripped text is shorter than
            ``MIN_TRANSCRIPTION_LENGTH``.
        """
        cleaned = value.strip()
        if len(cleaned) < MIN_TRANSCRIPTION_LENGTH:
            raise ValueError(
                f"transcription must be at least {MIN_TRANSCRIPTION_LENGTH} "
                f"characters after trimming whitespace (got {len(cleaned)})"
            )
        return cleaned


class EstimationResponse(BaseModel):
    """Successful estimation generated via CAG + LLM."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "estimation": (
                        "## Estimation: Landing + HubSpot blog\n\n"
                        "### Scope\nMVP landing, form, HubSpot, blog WYSIWYG.\n\n"
                        "### Task breakdown\n"
                        "| Task | Hours | Role |\n|---|---:|---|\n"
                        "| Landing from Figma | 16 | Frontend |\n"
                    ),
                    "confidence": 0.78,
                    "confidence_rationale": (
                        "Design exists in Figma and scope is clear; HubSpot plan "
                        "limits are still unknown."
                    ),
                    "model": "gpt-4o-mini",
                    "provider": "openai",
                    "prompt_tokens": 4200,
                    "completion_tokens": 650,
                    "timestamp": "2026-10-18T18:00:00Z",
                }
            ]
        }
    )

    estimation: str = Field(
        ...,
        description="Generated estimation in Markdown (tasks, hours, team, risks).",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Model self-assessed confidence for this estimate "
            "(0.0 = guess, 1.0 = very sure)."
        ),
        examples=[0.78],
    )
    confidence_rationale: str = Field(
        ...,
        description="Short explanation of why this confidence value was chosen.",
        examples=[
            "Clear Figma design and timeline; HubSpot plan limits unknown."
        ],
    )
    model: str = Field(
        ...,
        description="LLM model id used for this response.",
        examples=["gpt-4o-mini", "claude-haiku-4-5"],
    )
    provider: str = Field(
        ...,
        description="LLM provider used for this response.",
        examples=["openai", "anthropic"],
    )
    prompt_tokens: int | None = Field(
        default=None,
        description="Input/prompt tokens reported by the provider, if available.",
        ge=0,
    )
    completion_tokens: int | None = Field(
        default=None,
        description="Completion/output tokens reported by the provider, if available.",
        ge=0,
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the estimation was generated.",
    )


class HealthResponse(BaseModel):
    """Liveness payload for load balancers and smoke checks."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"status": "ok"}]}
    )

    status: str = Field(
        ...,
        description="Service status. `ok` means the process is up.",
        examples=["ok"],
    )


class ErrorResponse(BaseModel):
    """Standard FastAPI error body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"detail": "LLM provider error: Incorrect API key provided"},
                {
                    "detail": [
                        {
                            "type": "missing",
                            "loc": ["body", "transcription"],
                            "msg": "Field required",
                            "input": {},
                        }
                    ]
                },
            ]
        }
    )

    detail: str | list[object] = Field(
        ...,
        description="Error detail: a string message or a validation error list.",
    )
