"""Unit tests for structural budget chunking."""

from __future__ import annotations

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.schemas import (
    Budget,
    BudgetComponent,
    ClientMetadata,
)


def _sample_budget() -> Budget:
    """Build a minimal valid budget with two components.

    :return: Budget fixture.
    :raises: Does not raise under normal operation.
    """
    return Budget(
        budget_id="BUD-2024-014",
        client_metadata=ClientMetadata(
            name="FintechCorp",
            sector="finance",
            country="ES",
        ),
        project_summary="Mobile banking API with OAuth 2.0",
        main_technology="ruby_on_rails",
        year=2024,
        total_estimated_hours=200,
        components=[
            BudgetComponent(
                component_id="AUTH-001",
                name="OAuth 2.0 authentication backend",
                description="OAuth flows with JWT session management.",
                tech_stack=["ruby_on_rails", "postgresql"],
                estimated_hours=120,
                complexity="high",
                dependencies=[],
            ),
            BudgetComponent(
                component_id="API-001",
                name="Account API",
                description="Balances and transfers.",
                tech_stack=["ruby_on_rails"],
                estimated_hours=80,
                complexity="medium",
                dependencies=["AUTH-001"],
            ),
        ],
    )


def test_chunker_one_chunk_per_component() -> None:
    """Produce exactly one chunk per component with traceable ids.

    :return: None.
    :raises AssertionError: If chunk count or ids are wrong.
    """
    chunks = JSONStructuralChunker().chunk([_sample_budget()])
    assert len(chunks) == 2
    assert chunks[0].chunk_id == "BUD-2024-014::AUTH-001"
    assert chunks[1].chunk_id == "BUD-2024-014::API-001"
    assert chunks[0].metadata.client_sector == "finance"
    assert chunks[0].metadata.estimated_hours == 120
    assert chunks[0].token_count > 0


def test_chunker_accepts_explicit_encoding_name() -> None:
    """Allow constructing the chunker with an explicit tiktoken encoding.

    :return: None.
    :raises AssertionError: If chunking fails with ``cl100k_base``.
    """
    chunks = JSONStructuralChunker(encoding_name="cl100k_base").chunk(
        [_sample_budget()]
    )
    assert len(chunks) == 2
    assert chunks[0].token_count > 0


def test_chunk_text_includes_parent_context() -> None:
    """Embed text should prepend project / sector / year context.

    :return: None.
    :raises AssertionError: If parent context is missing from chunk text.
    """
    chunk = JSONStructuralChunker().chunk([_sample_budget()])[0]
    assert "[Project: Mobile banking API with OAuth 2.0]" in chunk.text
    assert "Client sector: finance" in chunk.text
    assert "Main tech: ruby_on_rails" in chunk.text
    assert "Component: OAuth 2.0 authentication backend" in chunk.text
    assert "Estimated hours: 120" in chunk.text
