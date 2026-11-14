"""Pydantic models for conversational estimation sessions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.estimation import EstimationResponse
from app.services.sessions import ProjectMetadata

CacheHitKind = Literal["none", "exact", "semantic"]


class CreateSessionResponse(BaseModel):
    """Payload returned when a new in-memory session is created."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"session_id": "550e8400-e29b-41d4-a716-446655440000"},
            ]
        }
    )

    session_id: str = Field(
        ...,
        description=(
            "UUID v4 identifying this conversation. Send it on later "
            "``POST /api/v1/sessions/{session_id}/estimate`` calls to reuse "
            "history and project metadata (process memory only)."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class TurnObserved(BaseModel):
    """Aggregated per-turn observation for CAG stress tests (CSV-friendly)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "turn_index": 1,
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    "enriched_transcript_chars": 240,
                    "attachments_total_chars": 0,
                    "messages_in_window": 3,
                    "anchors_count": 0,
                    "summary_chars": 0,
                    "tokens_in": 1200,
                    "tokens_out": 400,
                    "cost_usd": 0.00042,
                    "latency_ms": 850.5,
                    "cache_hit_kind": "none",
                    "last_resolved_tier": None,
                }
            ]
        }
    )

    turn_index: int = Field(..., ge=1, description="1-based turn index within the session.")
    session_id: str = Field(..., description="Session UUID for this observation.")
    enriched_transcript_chars: int = Field(
        ...,
        ge=0,
        description="Character count of transcript plus attachment payload sizes.",
    )
    attachments_total_chars: int = Field(
        ...,
        ge=0,
        description="Sum of raw attachment byte lengths (0 when none).",
    )
    messages_in_window: int = Field(
        ...,
        ge=0,
        description="Messages retained after sliding-window trim (system + turns).",
    )
    anchors_count: int = Field(
        default=0,
        ge=0,
        description="Anchor count (0 until summarizer/anchors land in a later module).",
    )
    summary_chars: int = Field(
        default=0,
        ge=0,
        description="Summary size (0 until cumulative summarizer lands).",
    )
    tokens_in: int | None = Field(
        default=None,
        description="Prompt tokens reported by the provider, if any.",
    )
    tokens_out: int | None = Field(
        default=None,
        description="Completion tokens reported by the provider, if any.",
    )
    cost_usd: float | None = Field(
        default=None,
        description="Estimated USD cost from the simple pricing table.",
    )
    latency_ms: float | None = Field(
        default=None,
        description="Wall-clock provider latency in milliseconds.",
    )
    cache_hit_kind: CacheHitKind = Field(
        default="none",
        description="Cache outcome; always ``none`` until caching is instrumented.",
    )
    last_resolved_tier: str | None = Field(
        default=None,
        description="Dynamic tier id when present; ``null`` in this CAG baseline.",
    )


class SessionEstimateResponse(EstimationResponse):
    """Multi-turn estimation plus the updated durable ``project_metadata``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": (
                        "## Estimation: Inventory alerts SaaS\n\n"
                        "| Phase | Hours | Notes |\n|---|---:|---|\n"
                        "| Discovery | 16 | From transcript + PDF |\n"
                    ),
                    "prompt_version": "v1",
                    "project_metadata": {
                        "project_name": "Inventory alerts SaaS",
                        "assumed_team_size": 2,
                        "mentioned_technologies": ["React", "Slack"],
                        "agreed_scope": "B2B SaaS dashboard for inventory alerts.",
                    },
                }
            ]
        }
    )

    project_metadata: ProjectMetadata = Field(
        ...,
        description=(
            "Durable project facts after this turn (memory, not chat history). "
            "Injected into the next system prompt as ``<project_metadata>``."
        ),
    )


class SessionSnapshotResponse(BaseModel):
    """Debug snapshot of an in-memory session for stress runners."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    "message_count": 5,
                    "turn_count": 2,
                    "anchors_count": 0,
                    "summary_chars": 0,
                    "last_resolved_tier": None,
                    "project_metadata": {
                        "project_name": "Inventory Hub",
                        "assumed_team_size": 3,
                        "mentioned_technologies": ["React"],
                        "agreed_scope": "MVP alerts",
                    },
                    "last_turn_observed": {
                        "turn_index": 2,
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "enriched_transcript_chars": 180,
                        "attachments_total_chars": 0,
                        "messages_in_window": 5,
                        "anchors_count": 0,
                        "summary_chars": 0,
                        "tokens_in": 900,
                        "tokens_out": 300,
                        "cost_usd": 0.0003,
                        "latency_ms": 700.0,
                        "cache_hit_kind": "none",
                        "last_resolved_tier": None,
                    },
                }
            ]
        }
    )

    session_id: str = Field(..., description="Session UUID.")
    message_count: int = Field(
        ...,
        ge=0,
        description="Messages in the sliding window including the system prompt.",
    )
    turn_count: int = Field(
        ...,
        ge=0,
        description="Complete user/assistant pairs currently retained.",
    )
    anchors_count: int = Field(
        default=0,
        ge=0,
        description="Always 0 in this baseline (no anchors yet).",
    )
    summary_chars: int = Field(
        default=0,
        ge=0,
        description="Always 0 in this baseline (no cumulative summary yet).",
    )
    last_resolved_tier: str | None = Field(
        default=None,
        description="Always null in this baseline (no dynamic tier yet).",
    )
    project_metadata: ProjectMetadata = Field(
        ...,
        description="Current durable project facts for the session.",
    )
    last_turn_observed: TurnObserved | None = Field(
        default=None,
        description="Most recent ``turn_observed`` payload, if any estimate ran.",
    )
