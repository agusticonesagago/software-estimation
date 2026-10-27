"""Static CAG context package."""

from app.context.examples import (
    CANONICAL_EXAMPLES,
    CanonicalExample,
    format_examples_for_prompt,
    load_cag_examples_markdown,
    select_examples,
)

__all__ = [
    "CANONICAL_EXAMPLES",
    "CanonicalExample",
    "format_examples_for_prompt",
    "load_cag_examples_markdown",
    "select_examples",
]
