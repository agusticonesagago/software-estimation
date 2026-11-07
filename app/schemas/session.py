"""Pydantic models for conversational estimation sessions."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.estimation import EstimationResponse
from app.services.sessions import ProjectMetadata


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
