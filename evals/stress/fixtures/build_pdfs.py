"""Generate calibrated synthetic PDFs for CAG attachment stress tests.

Produces ``attach_{5,20,50,100}kb.pdf`` under this fixtures directory.
``0 KB`` is represented by *no* file (runner omits the multipart part).

Do not commit the generated PDFs — regenerate with::

    uv run python -m evals.stress.fixtures.build_pdfs
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fpdf import FPDF

FIXTURES_DIR = Path(__file__).resolve().parent

# Kilobyte targets from the exercise (0 KB = no attachment).
ATTACHMENT_SIZES_KB: tuple[int, ...] = (0, 5, 20, 50, 100)
GENERATED_SIZES_KB: tuple[int, ...] = (5, 20, 50, 100)

_LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    "Warehouse SKU thresholds, alert acknowledgements, and audit trails "
    "appear so the model has extractable prose under attachment load. "
)


def pdf_filename(size_kb: int) -> str:
    """Return the canonical PDF filename for a non-zero size.

    :arg size_kb: Target size in kibibytes (must be one of 5/20/50/100).
    :return: Filename such as ``attach_20kb.pdf``.
    :raises ValueError: If ``size_kb`` is not a generated size.
    """
    if size_kb not in GENERATED_SIZES_KB:
        raise ValueError(
            f"size_kb must be one of {GENERATED_SIZES_KB}, got {size_kb}"
        )
    return f"attach_{size_kb}kb.pdf"


def pdf_path(size_kb: int, *, directory: Path | None = None) -> Path:
    """Resolve the output path for a generated attachment PDF.

    :arg size_kb: Target size in kibibytes.
    :arg directory: Output directory (default: this fixtures folder).
    :return: Absolute path to the PDF file.
    :raises ValueError: If ``size_kb`` is not a generated size.
    """
    root = directory if directory is not None else FIXTURES_DIR
    return (root / pdf_filename(size_kb)).resolve()


def marker_for_size(size_kb: int) -> str:
    """Stable recall marker embedded in each synthetic PDF.

    :arg size_kb: Target size in kibibytes.
    :return: Unique marker string for later content-recall checks.
    :raises: Does not raise under normal operation.
    """
    return f"STRESS_ATTACHMENT_MARKER_{size_kb}KB"


def _base_pdf_bytes(size_kb: int) -> bytes:
    """Render a small valid PDF that embeds the recall marker and filler prose.

    :arg size_kb: Size label used in the marker / title.
    :return: Raw PDF bytes (typically a few KiB before padding).
    :raises: Does not raise under normal operation.
    """
    marker = marker_for_size(size_kb)
    pdf = FPDF()
    # Uncompressed streams keep the marker searchable as plain bytes in tests.
    pdf.set_compression(False)
    pdf.set_title(marker)
    pdf.set_subject(f"CAG stress attachment fixture {size_kb}KB")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.cell(
        0,
        6,
        f"CAG stress fixture - target {size_kb} KB",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", style="B", size=11)
    pdf.cell(0, 6, marker, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", size=10)
    block = (_LOREM + " ") * 4
    for index in range(12):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, f"[{index + 1}] {block}")
    return bytes(pdf.output())


def _pad_pdf_to_size(base: bytes, target_bytes: int, *, marker: str) -> bytes:
    """Grow a PDF to at least ``target_bytes`` using comment padding before EOF.

    :arg base: Valid PDF bytes from fpdf2.
    :arg target_bytes: Minimum output size in bytes.
    :arg marker: Recall marker also stored in the padding comment.
    :return: PDF bytes with ``len >= target_bytes``.
    :raises ValueError: If ``base`` is not a PDF ending with ``%%EOF``.
    """
    stripped = base.rstrip()
    eof = b"%%EOF"
    if not stripped.endswith(eof):
        raise ValueError("Expected PDF body to end with %%EOF")
    stem = stripped[: -len(eof)].rstrip(b"\r\n")
    marker_line = f"\n% {marker}\n".encode("ascii")
    if len(stem) + len(marker_line) + len(eof) + 1 >= target_bytes:
        return stem + marker_line + eof + b"\n"
    # Final layout: stem + marker_line + %padding\\n + %%EOF\\n
    overhead = len(marker_line) + 1 + 1 + len(eof) + 1  # % + pad + \\n + EOF + \\n
    need = max(0, target_bytes - len(stem) - overhead)
    padding = marker_line + b"%" + (b"P" * need) + b"\n" + eof + b"\n"
    return stem + padding


def build_pdf_for_size(
    size_kb: int,
    *,
    directory: Path | None = None,
) -> Path:
    """Create one PDF whose on-disk size is at least ``size_kb`` KiB.

    Builds a small fpdf2 document (with a recall marker), then pads with PDF
    comments so the file reaches the calibrated byte length quickly.

    :arg size_kb: Target kibibytes (5, 20, 50, or 100).
    :arg directory: Output directory (default: fixtures dir).
    :return: Path to the written PDF.
    :raises ValueError: If ``size_kb`` is invalid or padding fails.
    :raises OSError: If the file cannot be written.
    """
    target = size_kb * 1024
    out = pdf_path(size_kb, directory=directory)
    out.parent.mkdir(parents=True, exist_ok=True)
    marker = marker_for_size(size_kb)
    payload = _pad_pdf_to_size(_base_pdf_bytes(size_kb), target, marker=marker)
    out.write_bytes(payload)
    return out


def build_all_pdfs(*, directory: Path | None = None) -> dict[int, Path]:
    """Generate every non-zero attachment fixture PDF.

    :arg directory: Output directory (default: fixtures dir).
    :return: Map of size_kb → written path.
    :raises ValueError: If any size cannot be materialized.
    :raises OSError: If a file cannot be written.
    """
    written: dict[int, Path] = {}
    for size_kb in GENERATED_SIZES_KB:
        written[size_kb] = build_pdf_for_size(size_kb, directory=directory)
    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for regenerating stress PDFs.

    :arg argv: Optional CLI args (defaults to ``sys.argv[1:]``).
    :return: Process exit code (``0`` on success).
    :raises: Does not raise under normal operation.
    """
    parser = argparse.ArgumentParser(
        description="Build synthetic attach_*kb.pdf fixtures for CAG stress.",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=FIXTURES_DIR,
        help="Output directory (default: evals/stress/fixtures).",
    )
    args = parser.parse_args(argv)
    paths = build_all_pdfs(directory=args.directory)
    for size_kb, path in paths.items():
        print(f"{size_kb:>4} KB -> {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
