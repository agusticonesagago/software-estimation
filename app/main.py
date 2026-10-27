"""FastAPI entrypoint for the software-estimation CAG API."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.config import get_settings
from app.logging_config import configure_logging
from app.routers.estimations import router as estimations_router
from app.schemas.estimation import HealthResponse

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Liveness and readiness style checks.",
    },
    {
        "name": "estimations",
        "description": (
            "Software estimation endpoints powered by CAG + an LLM provider "
            "(OpenAI or Anthropic)."
        ),
    },
]

OPENAPI_DESCRIPTION = """
## Overview

**software-estimation** turns a meeting transcription into a structured software
estimation (Markdown) using **CAG** (Cache-Augmented Generation).

Static few-shot examples live in `app/context/examples.py`
(`CANONICAL_EXAMPLES`) and are injected into every LLM system prompt. There is
no database, no vector retrieval, and no multi-turn chat.



## Authentication

This API does not expose end-user auth. LLM credentials are configured via
server environment variables (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`).

## Typical flow

1. `GET /health` - confirm the service is up
2. `POST /api/v1/estimate` - send `{ "transcription": "..." }`
3. Read `estimation` (Markdown) plus `model` / `provider` metadata
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
    summary="CAG-based software estimation API",
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
