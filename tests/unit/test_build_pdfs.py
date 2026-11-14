"""Unit tests for synthetic stress-test PDF fixtures."""

from pathlib import Path

import pytest

from evals.stress.fixtures.build_pdfs import (
    ATTACHMENT_SIZES_KB,
    GENERATED_SIZES_KB,
    build_all_pdfs,
    build_pdf_for_size,
    marker_for_size,
    pdf_filename,
    pdf_path,
)


def test_attachment_size_matrix_includes_zero_baseline() -> None:
    """Exercise matrix lists 0 KB plus the four generated sizes.

    :return: None.
    :raises AssertionError: If the size tuple is wrong.
    """
    assert ATTACHMENT_SIZES_KB == (0, 5, 20, 50, 100)
    assert GENERATED_SIZES_KB == (5, 20, 50, 100)


def test_pdf_filename_and_marker_helpers() -> None:
    """Filename and recall marker follow the attach_*kb convention.

    :return: None.
    :raises AssertionError: If naming drifts from the exercise contract.
    """
    assert pdf_filename(20) == "attach_20kb.pdf"
    assert marker_for_size(50) == "STRESS_ATTACHMENT_MARKER_50KB"
    with pytest.raises(ValueError):
        pdf_filename(0)


def test_build_pdf_for_size_meets_minimum_bytes(tmp_path: Path) -> None:
    """Each generated PDF is at least the nominal kibibyte target.

    :arg tmp_path: Pytest temporary directory.
    :return: None.
    :raises AssertionError: If size or marker content is wrong.
    """
    path = build_pdf_for_size(5, directory=tmp_path)
    assert path == pdf_path(5, directory=tmp_path)
    assert path.is_file()
    assert path.stat().st_size >= 5 * 1024
    raw = path.read_bytes()
    assert raw.startswith(b"%PDF")
    assert marker_for_size(5).encode("latin-1") in raw or marker_for_size(5) in raw.decode(
        "latin-1",
        errors="ignore",
    )


def test_build_all_pdfs_writes_four_files(tmp_path: Path) -> None:
    """``build_all_pdfs`` materializes 5/20/50/100 KB fixtures.

    :arg tmp_path: Pytest temporary directory.
    :return: None.
    :raises AssertionError: If any size is missing or undersized.
    """
    written = build_all_pdfs(directory=tmp_path)
    assert set(written) == set(GENERATED_SIZES_KB)
    for size_kb, path in written.items():
        assert path.exists()
        assert path.stat().st_size >= size_kb * 1024
