"""OpenAI ``text-embedding-3-small`` client with batched calls and retries."""

from __future__ import annotations

import time

from openai import OpenAI, RateLimitError

from app.embedding_pipeline.schemas import Chunk, EmbeddedChunk
from app.logging_config import get_tracer_logger

# List price for text-embedding-3-small (USD per 1M input tokens). Update when
# OpenAI changes published rates — used only for stats.estimated_cost_usd.
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_PRICE_USD_PER_1M_TOKENS = 0.02
DEFAULT_BATCH_SIZE = 100
_RETRY_WAITS_SECONDS = (1.0, 2.0, 4.0)

_trace = get_tracer_logger()


def estimate_embedding_cost_usd(total_tokens: int) -> float:
    """Estimate USD cost for embedding ``total_tokens`` input tokens.

    :arg total_tokens: Aggregate input tokens across chunks.
    :return: Non-negative estimated cost in USD.
    :raises: Does not raise under normal operation.
    """
    return max(0, int(total_tokens)) / 1_000_000.0 * EMBEDDING_PRICE_USD_PER_1M_TOKENS


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """Compute cosine similarity with the standard library only.

    :arg vector_a: First embedding vector.
    :arg vector_b: Second embedding vector.
    :return: Cosine similarity in ``[-1.0, 1.0]``, or ``0.0`` if a norm is zero.
    :raises ValueError: If the vectors have different lengths.
    """
    if len(vector_a) != len(vector_b):
        raise ValueError(
            f"Vector length mismatch: {len(vector_a)} != {len(vector_b)}"
        )
    dot = sum(a * b for a, b in zip(vector_a, vector_b, strict=True))
    norm_a = sum(a * a for a in vector_a) ** 0.5
    norm_b = sum(b * b for b in vector_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class OpenAIEmbedder:
    """Embed texts via OpenAI Embeddings API (batched)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = EMBEDDING_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        client: OpenAI | None = None,
    ) -> None:
        """Create an embedder.

        :arg api_key: OpenAI API key; falls back to ``OPENAI_API_KEY`` env when omitted.
        :arg model: Embedding model id.
        :arg batch_size: Max texts per ``embeddings.create`` call.
        :arg client: Optional pre-built OpenAI client (tests inject a fake).
        :return: None.
        :raises ValueError: If ``batch_size`` is less than 1.
        """
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self._model = model
        self._batch_size = batch_size
        self._client = client or OpenAI(api_key=api_key)
        self.last_total_tokens: int = 0
        self.last_estimated_cost_usd: float = 0.0

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text string.

        :arg text: Non-empty text to embed.
        :return: Embedding vector (1536 floats for the default model).
        :raises ValueError: If ``text`` is empty or whitespace-only.
        :raises RateLimitError: If retries are exhausted.
        :raises Exception: Propagates other OpenAI / network errors.
        """
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("text must be non-empty")
        vectors = self._embed_texts([cleaned])
        return vectors[0]

    def embed_many(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Embed many chunks in batches and return ``EmbeddedChunk`` rows.

        Updates ``last_total_tokens`` and ``last_estimated_cost_usd`` from the
        sum of chunk ``token_count`` values (pre-API tiktoken counts).

        :arg chunks: Chunks produced by ``JSONStructuralChunker``.
        :return: Chunks with ``embedding`` attached, same order as input.
        :raises RateLimitError: If retries are exhausted.
        :raises Exception: Propagates other OpenAI / network errors.
        """
        if not chunks:
            self.last_total_tokens = 0
            self.last_estimated_cost_usd = 0.0
            return []

        total_tokens = sum(chunk.token_count for chunk in chunks)
        embedded: list[EmbeddedChunk] = []
        for start in range(0, len(chunks), self._batch_size):
            batch = chunks[start : start + self._batch_size]
            batch_tokens = sum(chunk.token_count for chunk in batch)
            started = time.perf_counter()
            vectors = self._embed_texts([chunk.text for chunk in batch])
            latency_ms = (time.perf_counter() - started) * 1000.0
            _trace.info(
                "embedding.batch_completed",
                model=self._model,
                batch_index=start // self._batch_size,
                chunk_count=len(batch),
                total_tokens=batch_tokens,
                latency_ms=round(latency_ms, 2),
            )
            for chunk, vector in zip(batch, vectors, strict=True):
                embedded.append(
                    EmbeddedChunk(
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        metadata=chunk.metadata,
                        token_count=chunk.token_count,
                        embedding=vector,
                    )
                )

        self.last_total_tokens = total_tokens
        self.last_estimated_cost_usd = estimate_embedding_cost_usd(total_tokens)
        return embedded

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings with exponential backoff on rate limits.

        :arg texts: Non-empty list of strings to embed in one API call.
        :return: Embedding vectors in the same order as ``texts``.
        :raises RateLimitError: If all retries fail with rate limiting.
        :raises Exception: Propagates non-rate-limit API errors immediately.
        """
        last_error: Exception | None = None
        for attempt, wait_s in enumerate((0.0, *_RETRY_WAITS_SECONDS)):
            if wait_s > 0:
                time.sleep(wait_s)
            try:
                response = self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                )
                ordered = sorted(response.data, key=lambda row: row.index)
                return [list(row.embedding) for row in ordered]
            except RateLimitError as exc:
                last_error = exc
                _trace.info(
                    "embedding.rate_limited",
                    model=self._model,
                    attempt=attempt + 1,
                    wait_s=wait_s if wait_s > 0 else _RETRY_WAITS_SECONDS[0],
                    error=str(exc),
                )
                continue
        assert last_error is not None
        raise last_error
