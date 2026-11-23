"""Structural JSON chunker: one budget component becomes one chunk."""

from __future__ import annotations

import tiktoken

from app.embedding_pipeline.schemas import Budget, BudgetComponent, Chunk, ChunkMetadata
from app.logging_config import get_tracer_logger

_EMBEDDING_MODEL = "text-embedding-3-small"
_trace = get_tracer_logger()


class JSONStructuralChunker:
    """Chunk historical budgets by component, with parent context in the text."""

    def __init__(self, encoding_name: str | None = None) -> None:
        """Create a chunker bound to the embedding model's tokenizer.

        :arg encoding_name: Optional tiktoken encoding override; defaults to the
            encoding for ``text-embedding-3-small``.
        :return: None.
        :raises KeyError: If ``encoding_name`` is unknown to tiktoken.
        """
        if encoding_name is None:
            self._encoding = tiktoken.encoding_for_model(_EMBEDDING_MODEL)
        else:
            self._encoding = tiktoken.get_encoding(encoding_name)

    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        """Convert budgets into one contextual chunk per component.

        :arg budgets: Validated historical budgets.
        :return: Chunks ready for embedding (no vectors yet).
        :raises: Does not raise under normal operation.
        """
        chunks: list[Chunk] = []
        for budget in budgets:
            for component in budget.components:
                text = self._format_chunk_text(budget, component)
                chunk_id = f"{budget.budget_id}::{component.component_id}"
                token_count = len(self._encoding.encode(text))
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        text=text,
                        metadata=ChunkMetadata(
                            budget_id=budget.budget_id,
                            component_id=component.component_id,
                            client_sector=budget.client_metadata.sector,
                            main_technology=budget.main_technology,
                            year=budget.year,
                            complexity=component.complexity,
                            estimated_hours=component.estimated_hours,
                        ),
                        token_count=token_count,
                    )
                )
        _trace.info(
            "embedding.chunker.completed",
            budget_count=len(budgets),
            chunk_count=len(chunks),
            total_tokens=sum(c.token_count for c in chunks),
        )
        return chunks

    @staticmethod
    def _format_chunk_text(budget: Budget, component: BudgetComponent) -> str:
        """Build the embeddable text with parent budget context headers.

        :arg budget: Parent budget providing project / client context.
        :arg component: Component that becomes this chunk.
        :return: Multi-line text to embed.
        :raises: Does not raise under normal operation.
        """
        tech_stack = ", ".join(component.tech_stack)
        return (
            f"[Project: {budget.project_summary}]\n"
            f"[Client sector: {budget.client_metadata.sector} | "
            f"Year: {budget.year} | Main tech: {budget.main_technology}]\n"
            f"\n"
            f"Component: {component.name}\n"
            f"Description: {component.description}\n"
            f"Tech stack: {tech_stack}\n"
            f"Complexity: {component.complexity}\n"
            f"Estimated hours: {component.estimated_hours}"
        )
