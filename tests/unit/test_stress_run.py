"""Unit tests for the CAG stress runner (dry-run / CSV helpers)."""

from pathlib import Path

import pytest

from evals.stress.run import (
    CSV_FIELDS,
    build_result_row,
    expected_row_count,
    parse_args,
    run_stress,
    write_csv,
)
from evals.stress.scenarios import TurnSpec


def test_parse_args_quick_and_default_row_floor() -> None:
    """Quick mode shrinks the matrix; default matrix is ≥ 50 rows.

    :return: None.
    :raises AssertionError: If CLI defaults miss the exercise floor.
    """
    quick = parse_args(["--dry-run", "--quick"])
    assert quick.scenarios == ("growing",)
    assert quick.attachment_sizes_kb == (0, 5)
    assert expected_row_count(quick) == 6

    full = parse_args([])
    assert expected_row_count(full) >= 50


def test_build_result_row_and_write_csv(tmp_path: Path) -> None:
    """Flatten observation + metrics into a CSV row and persist it.

    :arg tmp_path: Pytest temporary directory.
    :return: None.
    :raises AssertionError: If CSV header/row shape is wrong.
    """
    turn = TurnSpec(
        turn_index=2,
        transcript="x" * 40,
        fact_to_remember="project name: Nimbus",
    )
    observed = {
        "turn_index": 2,
        "session_id": "sess",
        "enriched_transcript_chars": 40,
        "attachments_total_chars": 0,
        "messages_in_window": 5,
        "anchors_count": 0,
        "summary_chars": 0,
        "tokens_in": 10,
        "tokens_out": 5,
        "cost_usd": 0.001,
        "latency_ms": 100.0,
        "cache_hit_kind": "none",
        "last_resolved_tier": None,
    }
    row = build_result_row(
        scenario="growing",
        n_turns=3,
        attachment_size_kb=0,
        repeat=1,
        turn=turn,
        prior_facts=["project name: Nimbus"],
        estimate_body={"text": "## Estimation: Nimbus"},
        snapshot={
            "session_id": "sess",
            "project_metadata": {
                "project_name": "Nimbus",
                "mentioned_technologies": [],
            },
            "last_turn_observed": observed,
        },
        latency_budget_ms=1000,
        cost_budget_usd=1.0,
    )
    assert row["memory_drift_passed"] == 1
    assert row["latency_budget_passed"] == 1
    assert set(CSV_FIELDS).issubset(row.keys())

    out = tmp_path / "results.csv"
    write_csv([row], out)
    text = out.read_text(encoding="utf-8")
    assert "memory_drift_score" in text.splitlines()[0]
    assert "growing" in text


@pytest.mark.asyncio
async def test_dry_run_quick_writes_six_rows(tmp_path: Path) -> None:
    """Dry-run quick matrix produces six CSV rows without a live API.

    :arg tmp_path: Pytest temporary directory.
    :return: None.
    :raises AssertionError: If row count or output path is wrong.
    """
    output = tmp_path / "results.csv"
    fixtures = tmp_path / "fixtures"
    config = parse_args(
        [
            "--dry-run",
            "--quick",
            "--output",
            str(output),
            "--fixtures-dir",
            str(fixtures),
        ]
    )
    rows = await run_stress(config)
    write_csv(rows, output)
    assert len(rows) == 6
    assert output.is_file()
    assert (fixtures / "attach_5kb.pdf").is_file()
    assert {row["scenario"] for row in rows} == {"growing"}
    assert {row["attachment_size_kb"] for row in rows} == {0, 5}
