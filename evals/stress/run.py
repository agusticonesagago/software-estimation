"""CAG stress runner: scenarios × attachment sizes × repeats → CSV rows.

Reads ``turn_observed`` from ``GET /api/v1/sessions/{id}`` (no log scraping).

Examples::

    # Dry-run (ASGI + mocked LLM, no API key / no spend)
    uv run python -m evals.stress.run --dry-run --output evals/stress/results.csv

    # Against a live API (costs real tokens)
    uv run python -m evals.stress.run --http http://localhost:8080 \\
        --scenarios growing,pivot,contradiction \\
        --attachment-sizes 0,5,20,50,100 \\
        --repeats 2 --n-turns 3 \\
        --output evals/stress/results.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import patch

import httpx

from evals.stress.fixtures.build_pdfs import (
    ATTACHMENT_SIZES_KB,
    FIXTURES_DIR,
    build_all_pdfs,
    marker_for_size,
    pdf_path,
)
from evals.stress.metrics import (
    AttachmentRecallMetric,
    CostBudgetMetric,
    LatencyBudgetMetric,
    MemoryDriftMetric,
)
from evals.stress.scenarios import (
    SCENARIO_NAMES,
    ScenarioName,
    TurnSpec,
    build_scenario,
)

DEFAULT_OUTPUT = Path("evals/stress/results.csv")
API_PREFIX = "/api/v1"

# Defaults chosen so a full matrix yields ≥ 50 CSV rows:
# 3 scenarios × 5 sizes × 2 repeats × 3 turns = 90.
DEFAULT_REPEATS = 2
DEFAULT_N_TURNS = 3
DEFAULT_LATENCY_BUDGET_MS = 30_000.0
DEFAULT_COST_BUDGET_USD = 0.50

TURN_OBSERVED_FIELDS: tuple[str, ...] = (
    "turn_index",
    "session_id",
    "enriched_transcript_chars",
    "attachments_total_chars",
    "messages_in_window",
    "anchors_count",
    "summary_chars",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "latency_ms",
    "cache_hit_kind",
    "last_resolved_tier",
)

CSV_FIELDS: tuple[str, ...] = (
    "scenario",
    "n_turns",
    "attachment_size_kb",
    "repeat",
    "fact_to_remember",
    "estimate_text_chars",
    *TURN_OBSERVED_FIELDS,
    "latency_budget_score",
    "latency_budget_passed",
    "cost_budget_score",
    "cost_budget_passed",
    "memory_drift_score",
    "memory_drift_passed",
    "attachment_recall_score",
    "attachment_recall_passed",
)


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    """CLI-resolved stress matrix configuration.

    :ivar base_url: HTTP origin (ignored when ``dry_run``).
    :ivar dry_run: Use in-process ASGI app with a mocked LLM.
    :ivar scenarios: Profile names to run.
    :ivar attachment_sizes_kb: Attachment sizes including ``0``.
    :ivar repeats: How many times to repeat each scenario×size cell.
    :ivar n_turns: Truncate each profile to this many turns.
    :ivar latency_budget_ms: Ceiling for ``LatencyBudgetMetric``.
    :ivar cost_budget_usd: Ceiling for ``CostBudgetMetric``.
    :ivar attach_every_turn: If false, attach PDF only on turn 1.
    :ivar output: CSV destination path.
    :ivar fixtures_dir: Where to read/write synthetic PDFs.
    """

    base_url: str
    dry_run: bool
    scenarios: tuple[ScenarioName, ...]
    attachment_sizes_kb: tuple[int, ...]
    repeats: int
    n_turns: int
    latency_budget_ms: float
    cost_budget_usd: float
    attach_every_turn: bool
    output: Path
    fixtures_dir: Path


def _parse_csv_list(raw: str) -> list[str]:
    """Split a comma-separated CLI list.

    :arg raw: Raw CLI string.
    :return: Stripped non-empty tokens.
    :raises: Does not raise under normal operation.
    """
    return [part.strip() for part in raw.split(",") if part.strip()]


def parse_args(argv: Sequence[str] | None = None) -> RunnerConfig:
    """Parse runner CLI arguments into a ``RunnerConfig``.

    :arg argv: Optional argv override (defaults to ``sys.argv[1:]``).
    :return: Validated configuration.
    :raises SystemExit: On argparse errors.
    """
    parser = argparse.ArgumentParser(
        description="Run CAG stress scenarios and write results.csv",
    )
    parser.add_argument(
        "--http",
        default="http://localhost:8080",
        help="Base URL of a running API (default: http://localhost:8080).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="In-process ASGI + mocked LLM (no network, no provider spend).",
    )
    parser.add_argument(
        "--scenarios",
        default=",".join(SCENARIO_NAMES),
        help="Comma-separated profiles (growing,pivot,contradiction).",
    )
    parser.add_argument(
        "--attachment-sizes",
        default=",".join(str(size) for size in ATTACHMENT_SIZES_KB),
        help="Comma-separated KB sizes including 0.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=DEFAULT_REPEATS,
        help=f"Repeats per scenario×size cell (default: {DEFAULT_REPEATS}).",
    )
    parser.add_argument(
        "--n-turns",
        type=int,
        default=DEFAULT_N_TURNS,
        help=f"Turns per session from each profile (default: {DEFAULT_N_TURNS}).",
    )
    parser.add_argument(
        "--latency-budget-ms",
        type=float,
        default=DEFAULT_LATENCY_BUDGET_MS,
        help="LatencyBudgetMetric ceiling in ms.",
    )
    parser.add_argument(
        "--cost-budget-usd",
        type=float,
        default=DEFAULT_COST_BUDGET_USD,
        help="CostBudgetMetric ceiling in USD.",
    )
    parser.add_argument(
        "--attach-every-turn",
        action="store_true",
        help="Attach the PDF on every turn (default: turn 1 only).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=FIXTURES_DIR,
        help="Directory for attach_*kb.pdf fixtures.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Small matrix for smoke (growing; sizes 0,5; repeats 1; n=3).",
    )
    args = parser.parse_args(argv)

    scenarios_raw = _parse_csv_list(args.scenarios)
    sizes_raw = [int(item) for item in _parse_csv_list(args.attachment_sizes)]
    scenarios: tuple[ScenarioName, ...]
    sizes: tuple[int, ...]
    repeats = args.repeats
    n_turns = args.n_turns
    if args.quick:
        scenarios = ("growing",)
        sizes = (0, 5)
        repeats = 1
        n_turns = 3
    else:
        for name in scenarios_raw:
            if name not in SCENARIO_NAMES:
                parser.error(f"Unknown scenario {name!r}; expected {SCENARIO_NAMES}")
        scenarios = tuple(scenarios_raw)  # type: ignore[assignment]
        for size in sizes_raw:
            if size not in ATTACHMENT_SIZES_KB:
                parser.error(
                    f"Unknown attachment size {size}; expected {ATTACHMENT_SIZES_KB}"
                )
        sizes = tuple(sizes_raw)
        if repeats < 1:
            parser.error("--repeats must be >= 1")
        if n_turns < 1:
            parser.error("--n-turns must be >= 1")

    return RunnerConfig(
        base_url=args.http.rstrip("/"),
        dry_run=bool(args.dry_run),
        scenarios=scenarios,
        attachment_sizes_kb=sizes,
        repeats=repeats,
        n_turns=n_turns,
        latency_budget_ms=args.latency_budget_ms,
        cost_budget_usd=args.cost_budget_usd,
        attach_every_turn=bool(args.attach_every_turn),
        output=args.output,
        fixtures_dir=args.fixtures_dir,
    )


def expected_row_count(config: RunnerConfig) -> int:
    """Compute how many CSV rows the matrix will produce.

    :arg config: Runner configuration.
    :return: ``scenarios × sizes × repeats × n_turns``.
    :raises: Does not raise under normal operation.
    """
    return (
        len(config.scenarios)
        * len(config.attachment_sizes_kb)
        * config.repeats
        * config.n_turns
    )


def ensure_pdf_fixtures(config: RunnerConfig) -> dict[int, Path]:
    """Regenerate any non-zero PDF sizes required by the matrix.

    :arg config: Runner configuration.
    :return: Map of size_kb → path for sizes ``> 0``.
    :raises OSError: If fixtures cannot be written.
    :raises ValueError: If PDF generation fails.
    """
    needed = [size for size in config.attachment_sizes_kb if size > 0]
    if not needed:
        return {}
    config.fixtures_dir.mkdir(parents=True, exist_ok=True)
    # Always rebuild for determinism (fast with comment padding).
    build_all_pdfs(directory=config.fixtures_dir)
    return {size: pdf_path(size, directory=config.fixtures_dir) for size in needed}


async def _create_session(client: httpx.AsyncClient) -> str:
    """POST ``/sessions`` and return the new id.

    :arg client: HTTPX async client.
    :return: ``session_id``.
    :raises httpx.HTTPStatusError: On non-success responses.
    """
    response = await client.post(f"{API_PREFIX}/sessions")
    response.raise_for_status()
    return str(response.json()["session_id"])


async def _estimate_turn(
    client: httpx.AsyncClient,
    *,
    session_id: str,
    transcript: str,
    pdf: Path | None,
) -> dict[str, Any]:
    """POST multipart estimate for one turn.

    :arg client: HTTPX async client.
    :arg session_id: Active session UUID.
    :arg transcript: User transcript.
    :arg pdf: Optional attachment path (``None`` for 0 KB).
    :return: JSON body of the estimate response.
    :raises httpx.HTTPStatusError: On non-success responses.
    """
    data = {"transcript": transcript}
    files = None
    file_handle = None
    try:
        if pdf is not None:
            file_handle = pdf.open("rb")
            files = {
                "attachments": (pdf.name, file_handle, "application/pdf"),
            }
        response = await client.post(
            f"{API_PREFIX}/sessions/{session_id}/estimate",
            data=data,
            files=files,
            timeout=180.0,
        )
        response.raise_for_status()
        return dict(response.json())
    finally:
        if file_handle is not None:
            file_handle.close()


async def _get_snapshot(
    client: httpx.AsyncClient,
    *,
    session_id: str,
) -> dict[str, Any]:
    """GET session snapshot including ``last_turn_observed``.

    :arg client: HTTPX async client.
    :arg session_id: Active session UUID.
    :return: Snapshot JSON.
    :raises httpx.HTTPStatusError: On non-success responses.
    """
    response = await client.get(f"{API_PREFIX}/sessions/{session_id}")
    response.raise_for_status()
    return dict(response.json())


def _mean(scores: Sequence[float]) -> float:
    """Arithmetic mean, or ``0.0`` for an empty sequence.

    :arg scores: Numeric scores.
    :return: Mean value.
    :raises: Does not raise under normal operation.
    """
    if not scores:
        return 0.0
    return float(sum(scores) / len(scores))


def build_result_row(
    *,
    scenario: str,
    n_turns: int,
    attachment_size_kb: int,
    repeat: int,
    turn: TurnSpec,
    prior_facts: Sequence[str],
    estimate_body: dict[str, Any],
    snapshot: dict[str, Any],
    latency_budget_ms: float,
    cost_budget_usd: float,
) -> dict[str, Any]:
    """Evaluate metrics and flatten one CSV row.

    :arg scenario: Profile name.
    :arg n_turns: Configured truncation length.
    :arg attachment_size_kb: Attachment size for this cell.
    :arg repeat: 1-based repeat index.
    :arg turn: Current turn specification.
    :arg prior_facts: Facts declared on earlier turns (for MemoryDrift).
    :arg estimate_body: Estimate JSON response.
    :arg snapshot: Session snapshot JSON.
    :arg latency_budget_ms: Latency ceiling.
    :arg cost_budget_usd: Cost ceiling.
    :return: Flat CSV row dict.
    :raises ValueError: If ``last_turn_observed`` is missing from the snapshot.
    """
    observed = snapshot.get("last_turn_observed")
    if not isinstance(observed, dict):
        raise ValueError(
            f"Snapshot for session {snapshot.get('session_id')!r} "
            "missing last_turn_observed"
        )

    latency = LatencyBudgetMetric(latency_budget_ms).evaluate(observed)
    cost = CostBudgetMetric(cost_budget_usd).evaluate(observed)

    drift_scores: list[float] = []
    for fact in prior_facts:
        if not fact:
            continue
        drift_scores.append(
            MemoryDriftMetric(fact, where=["metadata", "summary", "anchors"])
            .evaluate(snapshot)
            .score
        )
    # On turn 1 there are no prior facts; treat as N/A → score 1.0 (nothing lost yet).
    if turn.turn_index == 1 or not drift_scores:
        drift_score = 1.0
        drift_passed = True
    else:
        drift_score = _mean(drift_scores)
        drift_passed = drift_score >= 1.0

    text = str(estimate_body.get("text") or "")
    if attachment_size_kb > 0:
        recall = AttachmentRecallMetric(
            marker_for_size(attachment_size_kb)
        ).evaluate(text)
        recall_score = recall.score
        recall_passed = recall.passed
    else:
        # No attachment → recall curve is N/A; count as pass for aggregates.
        recall_score = 1.0
        recall_passed = True

    row: dict[str, Any] = {
        "scenario": scenario,
        "n_turns": n_turns,
        "attachment_size_kb": attachment_size_kb,
        "repeat": repeat,
        "fact_to_remember": turn.fact_to_remember,
        "estimate_text_chars": len(text),
        "latency_budget_score": latency.score,
        "latency_budget_passed": int(latency.passed),
        "cost_budget_score": cost.score,
        "cost_budget_passed": int(cost.passed),
        "memory_drift_score": drift_score,
        "memory_drift_passed": int(drift_passed),
        "attachment_recall_score": recall_score,
        "attachment_recall_passed": int(recall_passed),
    }
    for field_name in TURN_OBSERVED_FIELDS:
        row[field_name] = observed.get(field_name)
    return row


def write_csv(rows: Sequence[dict[str, Any]], output: Path) -> None:
    """Write result rows to ``output`` with a stable header.

    :arg rows: Flattened CSV row dicts.
    :arg output: Destination path.
    :return: None.
    :raises OSError: If the file cannot be written.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in CSV_FIELDS})


async def run_stress(config: RunnerConfig) -> list[dict[str, Any]]:
    """Execute the full stress matrix and return CSV rows.

    :arg config: Runner configuration.
    :return: List of row dicts (also written by the caller).
    :raises httpx.HTTPError: On transport/HTTP failures.
    :raises ValueError: If snapshots lack ``turn_observed``.
    """
    pdfs = ensure_pdf_fixtures(config)
    rows: list[dict[str, Any]] = []

    async def _execute(client: httpx.AsyncClient) -> None:
        """Run the nested scenario loops against ``client``.

        :arg client: Connected HTTPX client.
        :return: None.
        :raises httpx.HTTPError: On request failures.
        :raises ValueError: If observations are missing.
        """
        for scenario in config.scenarios:
            turns = build_scenario(scenario, config.n_turns)
            for size_kb in config.attachment_sizes_kb:
                pdf = pdfs.get(size_kb)
                for repeat in range(1, config.repeats + 1):
                    session_id = await _create_session(client)
                    prior_facts: list[str] = []
                    for turn in turns:
                        use_pdf = pdf if (
                            size_kb > 0
                            and (
                                config.attach_every_turn
                                or turn.turn_index == 1
                            )
                        ) else None
                        estimate_body = await _estimate_turn(
                            client,
                            session_id=session_id,
                            transcript=turn.transcript,
                            pdf=use_pdf,
                        )
                        snapshot = await _get_snapshot(
                            client,
                            session_id=session_id,
                        )
                        row = build_result_row(
                            scenario=scenario,
                            n_turns=config.n_turns,
                            attachment_size_kb=size_kb,
                            repeat=repeat,
                            turn=turn,
                            prior_facts=prior_facts,
                            estimate_body=estimate_body,
                            snapshot=snapshot,
                            latency_budget_ms=config.latency_budget_ms,
                            cost_budget_usd=config.cost_budget_usd,
                        )
                        rows.append(row)
                        if turn.fact_to_remember:
                            prior_facts.append(turn.fact_to_remember)

    if config.dry_run:
        from app.main import app
        from app.schemas.llm import LLMResult
        from app.services.attachments import UploadedAttachment
        from app.services.sessions import session_store

        session_store.clear()

        def _fake_generate(*_args: Any, **kwargs: Any) -> LLMResult:
            """Return a deterministic fake estimation for dry-run.

            :arg _args: Positional LLM args (ignored).
            :arg kwargs: May include ``attachments`` from the service call.
            :return: Synthetic ``LLMResult`` with tokens/cost/latency.
            :raises: Does not raise under normal operation.
            """
            attachments = kwargs.get("attachments") or ()
            markers = ""
            if attachments:
                markers = " ".join(
                    marker_for_size(size)
                    for size in config.attachment_sizes_kb
                    if size > 0
                )
            text = (
                "## Estimation: Nimbus\n\n"
                "### Scope\n"
                "Warehouse alerts MVP with Flutter-ready notes.\n\n"
                "project name: Nimbus\n"
                "stack includes Flutter\n"
                "budget locked: 30000 EUR\n"
                f"{markers}\n"
            )
            return LLMResult(
                estimation=text,
                model="gpt-4o-mini",
                provider="openai",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=12.0,
                cost_usd=0.000045,
            )

        def _fake_upload(
            *,
            files: list[tuple[str, bytes, str | None]],
            settings: object,
        ) -> list[UploadedAttachment]:
            """Skip provider Files API during dry-run.

            :arg files: Raw upload tuples from the router.
            :arg settings: Unused settings object.
            :return: Synthetic Path A attachments (empty when no files).
            :raises: Does not raise under normal operation.
            """
            if not files:
                return []
            return [
                UploadedAttachment(
                    filename=files[0][0],
                    content_type="application/pdf",
                    size_bytes=len(files[0][1]),
                    file_id="file-dry-run",
                )
            ]

        transport = httpx.ASGITransport(app=app)
        with (
            patch("app.routers.sessions.upload_attachments", new=_fake_upload),
            patch(
                "app.routers.sessions.LLMService.generate_from_messages",
                new=_fake_generate,
            ),
        ):
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                await _execute(client)
        session_store.clear()
    else:
        async with httpx.AsyncClient(base_url=config.base_url) as client:
            await _execute(client)

    return rows


async def async_main(argv: Sequence[str] | None = None) -> int:
    """Async CLI entry: run matrix, write CSV, print summary.

    :arg argv: Optional CLI argv override.
    :return: Process exit code (``0`` on success).
    :raises: Propagates unexpected runner errors.
    """
    config = parse_args(argv)
    expected = expected_row_count(config)
    print(
        f"matrix: scenarios={list(config.scenarios)} "
        f"sizes={list(config.attachment_sizes_kb)} "
        f"repeats={config.repeats} n_turns={config.n_turns} "
        f"-> {expected} rows "
        f"({'dry-run' if config.dry_run else config.base_url})",
        file=sys.stderr,
    )
    rows = await run_stress(config)
    write_csv(rows, config.output)
    print(
        f"wrote {len(rows)} rows -> {config.output.resolve()}",
        file=sys.stderr,
    )
    if len(rows) < 50 and not config.dry_run:
        print(
            "warning: CSV has fewer than 50 rows; raise --repeats/--n-turns "
            "or include more --attachment-sizes for the exercise minimum.",
            file=sys.stderr,
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous CLI wrapper around ``async_main``.

    :arg argv: Optional CLI argv override.
    :return: Process exit code.
    :raises: Propagates unexpected runner errors.
    """
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
