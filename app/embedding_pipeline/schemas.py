"""Pydantic models for the budget embedding ingest pipeline."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ClientSector(StrEnum):
    """Closed set of client business sectors for budget metadata."""

    FINANCE = "finance"
    E_COMMERCE = "e-commerce"
    HEALTHCARE = "healthcare"
    INDUSTRIAL = "industrial"
    EDUCATION = "education"
    LOGISTICS = "logistics"
    MEDIA = "media"
    OTHER = "other"


class ComplexityLevel(StrEnum):
    """Relative complexity label for a budget component."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


EMBEDDING_DIMENSIONS = 1536


class ClientMetadata(BaseModel):
    """Client organisation metadata attached to a historical budget."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Client organisation name.",
        examples=["FintechCorp"],
    )
    sector: ClientSector = Field(
        ...,
        description="Business sector used for filtering (not embedded alone).",
        examples=["finance"],
    )
    country: str = Field(
        ...,
        min_length=2,
        max_length=8,
        description="ISO-style country code.",
        examples=["ES"],
    )


class BudgetComponent(BaseModel):
    """One billable component inside a historical budget."""

    component_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Stable component identifier within the budget.",
        examples=["AUTH-001"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short component title.",
        examples=["OAuth 2.0 authentication backend"],
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="Detailed scope of the component.",
    )
    tech_stack: list[str] = Field(
        ...,
        min_length=1,
        description="Technologies used to implement this component.",
        examples=[["ruby_on_rails", "postgresql", "redis"]],
    )
    estimated_hours: int = Field(
        ...,
        ge=1,
        description="Estimated delivery hours for this component.",
        examples=[120],
    )
    complexity: ComplexityLevel = Field(
        ...,
        description="Relative complexity label.",
        examples=["high"],
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Other ``component_id`` values this component depends on.",
    )


class Budget(BaseModel):
    """One normalised historical budget used as embedding source."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "budget_id": "BUD-2024-014",
                    "client_metadata": {
                        "name": "FintechCorp",
                        "sector": "finance",
                        "country": "ES",
                    },
                    "project_summary": (
                        "Mobile banking API with OAuth 2.0 authentication "
                        "and PSD2 compliance"
                    ),
                    "main_technology": "ruby_on_rails",
                    "year": 2024,
                    "total_estimated_hours": 480,
                    "components": [
                        {
                            "component_id": "AUTH-001",
                            "name": "OAuth 2.0 authentication backend",
                            "description": (
                                "Implementation of OAuth 2.0 flows with JWT "
                                "session management."
                            ),
                            "tech_stack": ["ruby_on_rails", "postgresql", "redis"],
                            "estimated_hours": 120,
                            "complexity": "high",
                            "dependencies": [],
                        }
                    ],
                }
            ]
        }
    )

    budget_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique budget identifier.",
        examples=["BUD-2024-014"],
    )
    client_metadata: ClientMetadata = Field(
        ...,
        description="Client organisation metadata.",
    )
    project_summary: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="One-line project summary.",
    )
    main_technology: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Primary technology / stack label for the project.",
        examples=["ruby_on_rails"],
    )
    year: int = Field(
        ...,
        ge=2000,
        le=2100,
        description="Budget year.",
        examples=[2024],
    )
    total_estimated_hours: int = Field(
        ...,
        ge=1,
        description="Sum of estimated hours across components.",
        examples=[480],
    )
    components: list[BudgetComponent] = Field(
        ...,
        min_length=1,
        description="Structural components; each becomes one chunk.",
    )


class ChunkMetadata(BaseModel):
    """Filterable fields that travel with a chunk but are not the embed text."""

    budget_id: str = Field(..., description="Parent budget id.")
    component_id: str = Field(..., description="Source component id.")
    client_sector: ClientSector = Field(..., description="Client sector.")
    main_technology: str = Field(..., description="Parent project main technology.")
    year: int = Field(..., description="Budget year.")
    complexity: ComplexityLevel = Field(..., description="Component complexity.")
    estimated_hours: int = Field(..., ge=1, description="Component estimated hours.")


class Chunk(BaseModel):
    """Text fragment ready to embed."""

    chunk_id: str = Field(
        ...,
        description="Traceable id ``{budget_id}::{component_id}``.",
        examples=["BUD-2024-014::AUTH-001"],
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Contextualised text that will be embedded.",
    )
    metadata: ChunkMetadata = Field(
        ...,
        description="Filterable metadata (not embedded as a separate vector).",
    )
    token_count: int = Field(
        ...,
        ge=0,
        description="Token count of ``text`` for ``text-embedding-3-small``.",
    )


class EmbeddedChunk(Chunk):
    """Chunk plus its dense embedding vector."""

    embedding: list[float] = Field(
        ...,
        min_length=EMBEDDING_DIMENSIONS,
        max_length=EMBEDDING_DIMENSIONS,
        description="Embedding vector (1536 dims for ``text-embedding-3-small``).",
    )


class IngestRequest(BaseModel):
    """HTTP body for ``POST /embeddings/ingest``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "budgets": [
                        {
                            "budget_id": "BUD-2024-014",
                            "client_metadata": {
                                "name": "FintechCorp",
                                "sector": "finance",
                                "country": "ES",
                            },
                            "project_summary": (
                                "Mobile banking API with OAuth 2.0 and PSD2"
                            ),
                            "main_technology": "ruby_on_rails",
                            "year": 2024,
                            "total_estimated_hours": 120,
                            "components": [
                                {
                                    "component_id": "AUTH-001",
                                    "name": "OAuth 2.0 authentication backend",
                                    "description": (
                                        "OAuth 2.0 flows with JWT session management."
                                    ),
                                    "tech_stack": [
                                        "ruby_on_rails",
                                        "postgresql",
                                        "redis",
                                    ],
                                    "estimated_hours": 120,
                                    "complexity": "high",
                                    "dependencies": [],
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    )

    budgets: list[Budget] = Field(
        ...,
        min_length=1,
        description="Historical budgets to chunk and embed.",
    )


class IngestStats(BaseModel):
    """Aggregated ingest statistics returned with the embedded chunks."""

    total_budgets: int = Field(..., ge=0, description="Number of budgets ingested.")
    total_chunks: int = Field(..., ge=0, description="Number of chunks produced.")
    total_tokens: int = Field(
        ...,
        ge=0,
        description="Sum of chunk ``token_count`` values sent to the embedder.",
    )
    estimated_cost_usd: float = Field(
        ...,
        ge=0.0,
        description="Estimated USD cost using ``text-embedding-3-small`` list price.",
    )


class IngestResponse(BaseModel):
    """HTTP response for ``POST /embeddings/ingest``."""

    chunks: list[EmbeddedChunk] = Field(
        ...,
        description="Vectorised chunks ready for later persistence / retrieval.",
    )
    stats: IngestStats = Field(
        ...,
        description="Aggregate counts and estimated embedding cost.",
    )


class ErrorResponse(BaseModel):
    """Generic error body for embedding pipeline failures."""

    detail: str = Field(..., description="Human-readable error message.")
