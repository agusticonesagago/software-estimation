"""Pydantic request/response models exposed in OpenAPI."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_DESCRIPTION_LENGTH = 20
MAX_DESCRIPTION_LENGTH = 2000
DEFAULT_PROMPT_VERSION = "v1"


class PromptVersion(str, Enum):
    """Supported Jinja2 prompt template directories under ``app/prompts/estimation/``."""

    V1 = "v1"
    V2 = "v2"


class ProjectType(str, Enum):
    """High-level project category for estimation prompts."""

    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    """How much detail the estimation should include."""

    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    """Preferred shape of the free-text estimation output."""

    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


class ReferenceProject(BaseModel):
    """A past project used as optional estimation context."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short name of the similar past project.",
        examples=["Warehouse alerts MVP"],
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="What was built and any outcome notes useful for comparison.",
        examples=[
            "React dashboard + Slack alerts; 96 hours over 4 weeks with one full-stack."
        ],
    )
    actual_hours: int | None = Field(
        default=None,
        ge=0,
        description="Actual delivery hours when known; omit if unknown.",
        examples=[96],
    )


class EstimationRequest(BaseModel):
    """Typed payload for generating a software estimation."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": (
                        "Build a B2B SaaS dashboard for inventory alerts with "
                        "role-based access, Slack notifications, and CSV export. "
                        "MVP in about 8 weeks; design is not ready yet."
                    ),
                    "project_type": "web_saas",
                    "detail_level": "medium",
                    "output_format": "phases_table",
                    "reference_projects": [
                        {
                            "name": "Warehouse alerts MVP",
                            "summary": (
                                "React dashboard + Slack alerts; delivered in "
                                "4 weeks by one full-stack engineer."
                            ),
                            "actual_hours": 96,
                        }
                    ],
                }
            ]
        }
    )

    description: str = Field(
        ...,
        min_length=MIN_DESCRIPTION_LENGTH,
        max_length=MAX_DESCRIPTION_LENGTH,
        description=(
            "Project description to estimate. "
            f"Must be {MIN_DESCRIPTION_LENGTH}–{MAX_DESCRIPTION_LENGTH} characters "
            "after trimming whitespace."
        ),
        examples=[
            "Build a B2B SaaS dashboard for inventory alerts with role-based "
            "access, Slack notifications, and CSV export."
        ],
    )
    project_type: ProjectType = Field(
        ...,
        description="Project category used to steer the estimation prompt.",
        examples=["web_saas"],
    )
    detail_level: DetailLevel = Field(
        ...,
        description="Amount of detail expected in the estimation.",
        examples=["medium"],
    )
    output_format: OutputFormat = Field(
        ...,
        description="Preferred free-text layout for the estimation.",
        examples=["phases_table"],
    )
    reference_projects: list[ReferenceProject] | None = Field(
        default=None,
        description=(
            "Optional similar past projects to ground the estimate. "
            "Omitted or null means no reference context is injected into the prompt."
        ),
    )

    @field_validator("description")
    @classmethod
    def description_must_meet_bounds(cls, value: str) -> str:
        """Reject blank or out-of-bounds descriptions after trimming.

        :arg value: Raw project description from the request body.
        :return: Stripped description when it meets length bounds.
        :raises ValueError: If the stripped text is outside the allowed range.
        """
        cleaned = value.strip()
        if len(cleaned) < MIN_DESCRIPTION_LENGTH:
            raise ValueError(
                f"description must be at least {MIN_DESCRIPTION_LENGTH} "
                f"characters after trimming whitespace (got {len(cleaned)})"
            )
        if len(cleaned) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"description must be at most {MAX_DESCRIPTION_LENGTH} "
                f"characters after trimming whitespace (got {len(cleaned)})"
            )
        return cleaned


class EstimationResponse(BaseModel):
    """Successful estimation generated via the configured LLM path."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": (
                        "## Estimation: Inventory alerts SaaS\n\n"
                        "| Phase | Hours | Notes |\n|---|---:|---|\n"
                        "| Discovery | 16 | Requirements workshop |\n"
                    ),
                    "prompt_version": "v1",
                }
            ]
        }
    )

    text: str = Field(
        ...,
        description="Generated estimation as free-text Markdown (or narrative).",
    )
    prompt_version: str = Field(
        ...,
        description="Prompt template version used to build system/user messages.",
        examples=["v1"],
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
                            "loc": ["body", "description"],
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
