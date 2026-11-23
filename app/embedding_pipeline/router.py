"""HTTP routes for the embedding ingest pipeline."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.embedder import OpenAIEmbedder
from app.embedding_pipeline.schemas import (
    ErrorResponse,
    IngestRequest,
    IngestResponse,
    IngestStats,
)
from app.logging_config import get_tracer_logger

router = APIRouter(tags=["embeddings"])
_trace = get_tracer_logger()


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Chunk and embed historical budgets",
    description=(
        "Accepts normalised historical budgets, splits each component into a "
        "contextual chunk (structural JSON chunking), and embeds them with "
        "OpenAI ``text-embedding-3-small``. Vectors are returned in memory; "
        "nothing is persisted yet (pgvector arrives in a later session)."
    ),
    response_description="Vectorised chunks plus aggregate ingest stats.",
    responses={
        status.HTTP_200_OK: {
            "description": "Chunks embedded successfully.",
            "model": IngestResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed Pydantic validation.",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Unexpected OpenAI / embedder failure.",
            "model": ErrorResponse,
        },
    },
)
def ingest_embeddings(body: IngestRequest) -> IngestResponse:
    """Chunk budgets and return OpenAI embeddings for each component.

    :arg body: Ingest payload with one or more budgets.
    :return: Embedded chunks and aggregate stats.
    :raises HTTPException: 500 when the embedding provider fails unexpectedly.
    """
    request_id = str(uuid4())
    settings = get_settings()
    _trace.info(
        "embedding.ingest.received",
        request_id=request_id,
        endpoint="POST /embeddings/ingest",
        budget_count=len(body.budgets),
        component_count=sum(len(b.components) for b in body.budgets),
    )

    chunker = JSONStructuralChunker()
    chunks = chunker.chunk(body.budgets)
    embedder = OpenAIEmbedder(api_key=settings.openai_api_key)

    try:
        embedded = embedder.embed_many(chunks)
    except Exception as exc:  # noqa: BLE001 - map provider failures to 500
        _trace.exception(
            "embedding.ingest.failed",
            request_id=request_id,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Embedding provider error",
        ) from exc

    response = IngestResponse(
        chunks=embedded,
        stats=IngestStats(
            total_budgets=len(body.budgets),
            total_chunks=len(embedded),
            total_tokens=embedder.last_total_tokens,
            estimated_cost_usd=embedder.last_estimated_cost_usd,
        ),
    )
    _trace.info(
        "embedding.ingest.completed",
        request_id=request_id,
        total_budgets=response.stats.total_budgets,
        total_chunks=response.stats.total_chunks,
        total_tokens=response.stats.total_tokens,
        estimated_cost_usd=response.stats.estimated_cost_usd,
    )
    return response
