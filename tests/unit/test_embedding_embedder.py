"""Unit tests for OpenAI embedder helpers and batched embedding."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openai import RateLimitError

from app.embedding_pipeline.embedder import (
    OpenAIEmbedder,
    cosine_similarity,
    estimate_embedding_cost_usd,
)
from app.embedding_pipeline.schemas import Chunk, ChunkMetadata, EMBEDDING_DIMENSIONS


def _fake_vector(seed: float) -> list[float]:
    """Build a deterministic unit-ish vector of the model dimension.

    :arg seed: Value placed in the first coordinate.
    :return: Embedding-sized float list.
    :raises: Does not raise under normal operation.
    """
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[0] = seed
    vector[1] = 1.0
    return vector


def _chunk(chunk_id: str, text: str) -> Chunk:
    """Build a minimal chunk for embedder tests.

    :arg chunk_id: Chunk identifier.
    :arg text: Embed text.
    :return: Chunk with tiny token_count.
    :raises: Does not raise under normal operation.
    """
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            budget_id="BUD-1",
            component_id="C-1",
            client_sector="finance",
            main_technology="python",
            year=2024,
            complexity="low",
            estimated_hours=10,
        ),
        token_count=8,
    )


def test_cosine_similarity_identical_vectors() -> None:
    """Identical vectors should score 1.0.

    :return: None.
    :raises AssertionError: If similarity is not ~1.
    """
    vector = [1.0, 0.0, 0.0]
    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors() -> None:
    """Orthogonal vectors should score 0.0.

    :return: None.
    :raises AssertionError: If similarity is not ~0.
    """
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_length_mismatch() -> None:
    """Mismatched lengths should raise ValueError.

    :return: None.
    :raises AssertionError: If ValueError is not raised.
    """
    with pytest.raises(ValueError, match="length mismatch"):
        cosine_similarity([1.0], [1.0, 2.0])


def test_estimate_embedding_cost_usd() -> None:
    """Cost should follow the $0.02 / 1M tokens constant.

    :return: None.
    :raises AssertionError: If cost math drifts.
    """
    assert estimate_embedding_cost_usd(1_000_000) == pytest.approx(0.02)
    assert estimate_embedding_cost_usd(500_000) == pytest.approx(0.01)


def test_embed_many_batches_and_preserves_order() -> None:
    """``embed_many`` should call the API once per batch and keep order.

    :return: None.
    :raises AssertionError: If batching or ordering is wrong.
    """
    client = MagicMock()
    client.embeddings.create.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(index=0, embedding=_fake_vector(0.1)),
            SimpleNamespace(index=1, embedding=_fake_vector(0.2)),
        ]
    )
    embedder = OpenAIEmbedder(client=client, batch_size=2)
    chunks = [
        _chunk("BUD-1::A", "alpha"),
        _chunk("BUD-1::B", "beta"),
    ]
    embedded = embedder.embed_many(chunks)
    assert len(embedded) == 2
    assert embedded[0].chunk_id == "BUD-1::A"
    assert embedded[0].embedding[0] == pytest.approx(0.1)
    assert embedder.last_total_tokens == 16
    assert embedder.last_estimated_cost_usd == pytest.approx(16 / 1_000_000 * 0.02)
    client.embeddings.create.assert_called_once()


def test_embed_one_retries_rate_limit_then_succeeds() -> None:
    """RateLimitError should retry with backoff then succeed.

    :return: None.
    :raises AssertionError: If retries do not recover.
    """
    client = MagicMock()
    client.embeddings.create.side_effect = [
        RateLimitError("slow down", response=MagicMock(status_code=429), body=None),
        SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=_fake_vector(0.5))]
        ),
    ]
    embedder = OpenAIEmbedder(client=client)
    # Avoid sleeping in unit tests.
    import app.embedding_pipeline.embedder as embedder_mod

    original_sleep = embedder_mod.time.sleep
    embedder_mod.time.sleep = lambda _s: None
    try:
        vector = embedder.embed_one("hello embeddings")
    finally:
        embedder_mod.time.sleep = original_sleep
    assert len(vector) == EMBEDDING_DIMENSIONS
    assert client.embeddings.create.call_count == 2


def test_embed_one_rejects_empty_text() -> None:
    """Empty text should raise before calling the API.

    :return: None.
    :raises AssertionError: If empty text is accepted.
    """
    embedder = OpenAIEmbedder(client=MagicMock())
    with pytest.raises(ValueError, match="non-empty"):
        embedder.embed_one("   ")


def test_embed_many_empty_list_resets_stats() -> None:
    """Empty input should return [] and zero cost stats.

    :return: None.
    :raises AssertionError: If stats are not reset.
    """
    embedder = OpenAIEmbedder(client=MagicMock())
    assert embedder.embed_many([]) == []
    assert embedder.last_total_tokens == 0
    assert embedder.last_estimated_cost_usd == 0.0


def test_embedder_rejects_invalid_batch_size() -> None:
    """batch_size < 1 should raise ValueError.

    :return: None.
    :raises AssertionError: If invalid batch size is accepted.
    """
    with pytest.raises(ValueError, match="batch_size"):
        OpenAIEmbedder(client=MagicMock(), batch_size=0)


def test_cosine_similarity_zero_norm() -> None:
    """Zero vectors should yield similarity 0.0.

    :return: None.
    :raises AssertionError: If zero-norm handling is wrong.
    """
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_embed_one_raises_after_rate_limit_retries_exhausted() -> None:
    """Exhausted rate-limit retries should re-raise RateLimitError.

    :return: None.
    :raises AssertionError: If RateLimitError is swallowed.
    """
    client = MagicMock()
    client.embeddings.create.side_effect = RateLimitError(
        "slow down",
        response=MagicMock(status_code=429),
        body=None,
    )
    embedder = OpenAIEmbedder(client=client)
    import app.embedding_pipeline.embedder as embedder_mod

    original_sleep = embedder_mod.time.sleep
    embedder_mod.time.sleep = lambda _s: None
    try:
        with pytest.raises(RateLimitError):
            embedder.embed_one("hello")
    finally:
        embedder_mod.time.sleep = original_sleep
