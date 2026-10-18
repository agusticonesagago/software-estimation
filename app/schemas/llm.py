"""Schemas for LLM provider payloads and service results (not HTTP)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator


class LLMEstimationPayload(BaseModel):
    """JSON object the model must return after a CAG estimation call."""

    estimation: str = Field(
        ...,
        min_length=1,
        description="Markdown estimation body.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Self-assessed confidence from 0.0 to 1.0.",
    )
    confidence_rationale: str = Field(
        default="",
        description="Short explanation of the confidence score.",
    )

    @field_validator("estimation")
    @classmethod
    def estimation_must_not_be_blank(cls, value: str) -> str:
        """Reject whitespace-only estimations.

        :arg value: Raw estimation string.
        :return: Stripped estimation.
        :raises ValueError: If empty after strip.
        """
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("estimation must be a non-empty string")
        return cleaned

    @field_validator("confidence_rationale")
    @classmethod
    def rationale_strip(cls, value: str) -> str:
        """Normalize rationale whitespace.

        :arg value: Raw rationale.
        :return: Stripped rationale.
        :raises: Does not raise under normal operation.
        """
        return value.strip()


@dataclass(frozen=True)
class LLMResult:
    """Normalized estimation result produced by ``LLMService``."""

    estimation: str
    model: str
    provider: str
    confidence: float
    confidence_rationale: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def parse_llm_estimation_payload(raw: str) -> LLMEstimationPayload:
    """Parse raw model text into a validated ``LLMEstimationPayload``.

    :arg raw: Raw model text (JSON object, optionally wrapped in fences).
    :return: Validated payload model.
    :raises ValueError: If JSON is invalid or required fields fail validation.
    """
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Model JSON must be an object")

    try:
        return LLMEstimationPayload.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - normalize to ValueError for callers
        raise ValueError(f"Invalid LLM estimation payload: {exc}") from exc
