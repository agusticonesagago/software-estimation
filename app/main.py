"""FastAPI entrypoint for the software-estimation API."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.config import get_settings
from app.logging_config import configure_logging
from app.routers.estimations import router as estimations_router
from app.routers.sessions import router as sessions_router
from app.schemas.estimation import HealthResponse

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Liveness and readiness style checks.",
    },
    {
        "name": "estimations",
        "description": (
            "Software estimation endpoints powered by versioned Jinja2 prompts "
            "and an LLM provider (OpenAI or Anthropic)."
        ),
    },
    {
        "name": "sessions",
        "description": (
            "In-memory conversational sessions (UUID ``session_id``) for "
            "multi-turn estimation. Not persisted across process restarts."
        ),
    },
]

OPENAPI_DESCRIPTION = """
## Overview

**software-estimation** turns a typed project description into a free-text
software estimation (Markdown) using an LLM provider (OpenAI or Anthropic).

The client sends a structured `EstimationRequest` (`description`,
`project_type`, `detail_level`, `output_format`). The service renders Jinja2
prompts (`app/prompts/estimation/<version>/`) and calls the LLM with separate
`system` / `user` roles. Pass `?prompt_version=v1|v2` (default `v1`). The
response is `{ "text": "...", "prompt_version": "..." }`.

## Authentication

This API does not expose end-user auth. LLM credentials are configured via
server environment variables (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`).

## Typical flow

1. `GET /health` - confirm the service is up
2. `POST /api/v1/sessions` - create a conversation and keep `session_id`
3. `POST /api/v1/estimate` - one-shot typed `EstimationRequest` (session 04)
4. Multi-turn estimate under `/api/v1/sessions/{session_id}/...` (session 05)
"""


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate settings before serving traffic.

    :arg _app: FastAPI application instance (unused).
    :return: Async iterator that yields once during application lifetime.
    :raises ValidationError: If the active provider API key is missing.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    title="software-estimation",
    summary="Typed software estimation API with versioned Jinja2 prompts",
    description=OPENAPI_DESCRIPTION,
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "Agustí Conesa Gago",
    },
    license_info={
        "name": "Proprietary",
    },
)

app.include_router(
    estimations_router,
    prefix="/api/v1",
)
app.include_router(
    sessions_router,
    prefix="/api/v1",
)


@app.get(
    "/",
    tags=["health"],
    summary="API root",
    description="Redirects to Swagger UI at `/docs`.",
    response_class=RedirectResponse,
    responses={
        status.HTTP_307_TEMPORARY_REDIRECT: {
            "description": "Redirect to Swagger UI.",
        },
    },
    include_in_schema=True,
)
def root() -> RedirectResponse:
    """Redirect the API root to Swagger documentation.

    :return: Temporary redirect to ``/docs``.
    :raises: Does not raise under normal operation.
    """
    return RedirectResponse(url="/docs", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get(
    "/health",
    tags=["health"],
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Returns service liveness. Used by CI smoke tests and probes.",
    response_description="Service is healthy.",
    responses={
        status.HTTP_200_OK: {
            "description": "Process is running.",
            "model": HealthResponse,
        },
    },
)
def health() -> HealthResponse:
    """Return service health status.

    :return: Payload with ``status=ok`` when the process is up.
    :raises: Does not raise under normal operation.
    """
    return HealthResponse(status="ok")


# Re-export for type checkers / OpenAPI lifespan docs references
__all__ = ["app", "health", "lifespan", "ValidationError"]
