"""Internal LLM service result types (not HTTP OpenAPI models)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResult:
    """Normalized free-text estimation result produced by ``LLMService``."""

    estimation: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
