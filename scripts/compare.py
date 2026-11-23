#!/usr/bin/env python3
"""CLI: embed two texts with OpenAI and print cosine similarity."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow ``uv run python scripts/compare.py`` from the repo root without install path tricks.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import get_settings  # noqa: E402
from app.embedding_pipeline.embedder import OpenAIEmbedder, cosine_similarity  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the compare script.

    :arg argv: Optional argument list (defaults to ``sys.argv[1:]``).
    :return: Parsed namespace with ``text_a`` and ``text_b``.
    :raises SystemExit: If required arguments are missing.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Embed two texts with text-embedding-3-small and print cosine similarity."
        )
    )
    parser.add_argument("--text-a", required=True, help="First text to embed.")
    parser.add_argument("--text-b", required=True, help="Second text to embed.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the comparison and print a short report.

    :arg argv: Optional CLI arguments.
    :return: Process exit code (0 on success).
    :raises SystemExit: Propagated from argument parsing failures.
    """
    load_dotenv(_ROOT / ".env")
    args = parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)

    embedder = OpenAIEmbedder(api_key=settings.openai_api_key)
    vector_a = embedder.embed_one(args.text_a)
    vector_b = embedder.embed_one(args.text_b)
    score = cosine_similarity(vector_a, vector_b)

    print(f"Text A: {args.text_a}")
    print(f"Text B: {args.text_b}")
    print(f"Cosine similarity: {score:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
