"""Synthetic multi-turn conversation profiles for CAG stress tests.

Each profile is a sequence of ``(turn_index, transcript, fact_to_remember)``.
``fact_to_remember`` strings feed ``MemoryDriftMetric`` on later turns
(case-insensitive match against the session snapshot).

Supported lengths ``N`` are ``{1, 3, 6, 10, 20}`` (truncate the full script).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScenarioName = Literal["growing", "pivot", "contradiction"]

# Lengths the runner should exercise by default (20 is optional / costly).
DEFAULT_N_TURNS: tuple[int, ...] = (1, 3, 6, 10)
ALL_N_TURNS: tuple[int, ...] = (1, 3, 6, 10, 20)

SCENARIO_NAMES: tuple[ScenarioName, ...] = ("growing", "pivot", "contradiction")


@dataclass(frozen=True, slots=True)
class TurnSpec:
    """One synthetic user turn plus the fact later turns should still know.

    :ivar turn_index: 1-based position in the scenario script.
    :ivar transcript: User text sent to ``POST .../estimate``.
    :ivar fact_to_remember: Short claim for ``MemoryDriftMetric`` (may be empty).
    """

    turn_index: int
    transcript: str
    fact_to_remember: str


def _t(turn_index: int, transcript: str, fact_to_remember: str = "") -> TurnSpec:
    """Build a ``TurnSpec`` with a normalized transcript.

    :arg turn_index: 1-based turn number.
    :arg transcript: Raw user transcript.
    :arg fact_to_remember: Optional durable claim for later recall checks.
    :return: Immutable turn specification.
    :raises ValueError: If ``turn_index`` is not positive or transcript is blank.
    """
    cleaned = " ".join(transcript.split())
    if turn_index < 1:
        raise ValueError(f"turn_index must be >= 1, got {turn_index}")
    if len(cleaned) < 20:
        raise ValueError(
            f"transcript for turn {turn_index} must be at least 20 characters"
        )
    return TurnSpec(
        turn_index=turn_index,
        transcript=cleaned,
        fact_to_remember=fact_to_remember.strip(),
    )


# ---------------------------------------------------------------------------
# growing — coherent Nimbus feature growth (cost curve + name survival)
# ---------------------------------------------------------------------------
_GROWING: tuple[TurnSpec, ...] = (
    _t(
        1,
        "We are kicking off a B2B SaaS called Nimbus for warehouse inventory "
        "alerts. Please draft a phased estimation for an MVP with a small team.",
        "project name: Nimbus",
    ),
    _t(
        2,
        "Nimbus needs email and Slack notifications when stock drops below a "
        "threshold. Keep the project name Nimbus in the plan.",
        "notifications: Slack and email",
    ),
    _t(
        3,
        "Add authentication for Nimbus: email/password plus optional SSO for "
        "enterprise tenants. Assume two backend engineers.",
        "auth: email password and SSO",
    ),
    _t(
        4,
        "Nimbus must be multi-tenant from day one. Isolate data per customer "
        "organization and support invite flows for warehouse managers.",
        "architecture: multi-tenant",
    ),
    _t(
        5,
        "Add an immutable audit log for every stock threshold change in Nimbus. "
        "Compliance will review who changed what and when.",
        "feature: immutable audit log",
    ),
    _t(
        6,
        "Warehouse leads want CSV export of alert history from Nimbus, filtered "
        "by site and date range, downloadable from the dashboard.",
        "feature: CSV export",
    ),
    _t(
        7,
        "Nimbus should include a React admin dashboard with charts for open "
        "alerts, acknowledgment rate, and stockout risk by warehouse.",
        "stack includes React",
    ),
    _t(
        8,
        "Persist Nimbus operational data in PostgreSQL. Plan migrations and a "
        "basic backup story for the first production release.",
        "stack includes PostgreSQL",
    ),
    _t(
        9,
        "Add role-based access in Nimbus: viewer, operator, and admin. Operators "
        "ack alerts; admins manage thresholds and tenants.",
        "feature: RBAC roles",
    ),
    _t(
        10,
        "Nimbus needs a public REST API so partner ERPs can push stock levels. "
        "Include API keys and rate limits in the estimate.",
        "feature: public REST API",
    ),
    _t(
        11,
        "Introduce webhook callbacks from Nimbus when an alert is acknowledged "
        "or auto-resolved after restock.",
        "feature: webhooks",
    ),
    _t(
        12,
        "Add scheduled digests for Nimbus: daily email summarizing open alerts "
        "per warehouse for managers who prefer batch updates.",
        "feature: scheduled digests",
    ),
    _t(
        13,
        "Nimbus should support CSV and Excel bulk import of SKU thresholds for "
        "large warehouses during onboarding.",
        "feature: bulk SKU import",
    ),
    _t(
        14,
        "Plan a staging environment for Nimbus with anonymized sample tenants "
        "and a smoke suite before each production deploy.",
        "ops: staging environment",
    ),
    _t(
        15,
        "Add observability for Nimbus: structured logs, basic metrics, and "
        "alerting when the ingestion pipeline lags.",
        "ops: observability",
    ),
    _t(
        16,
        "Nimbus mobile-friendly acknowledgment: operators must ack critical "
        "alerts from a phone browser without a native app yet.",
        "ux: mobile-friendly ack",
    ),
    _t(
        17,
        "Include a soft delete and retention policy for Nimbus alert history so "
        "old noise can be archived after twelve months.",
        "policy: twelve-month retention",
    ),
    _t(
        18,
        "Nimbus needs i18n for English and Spanish UI strings on the dashboard "
        "and notification templates.",
        "feature: i18n EN ES",
    ),
    _t(
        19,
        "Estimate a hardening sprint for Nimbus: dependency updates, secrets "
        "rotation, and a lightweight threat model review.",
        "ops: security hardening sprint",
    ),
    _t(
        20,
        "Final pass: keep the project name Nimbus explicit in the summary and "
        "confirm MVP scope still matches the original warehouse alerts pitch.",
        "project name: Nimbus",
    ),
)


# ---------------------------------------------------------------------------
# pivot — React stack then switch to Flutter at turn 5
# ---------------------------------------------------------------------------
_PIVOT: tuple[TurnSpec, ...] = (
    _t(
        1,
        "Estimate FieldSync, a field-service scheduling tool. We plan a React "
        "web client and a small FastAPI backend for the MVP.",
        "project name: FieldSync",
    ),
    _t(
        2,
        "FieldSync technicians will use the React UI to claim jobs, update "
        "status, and upload completion photos from a laptop.",
        "stack includes React",
    ),
    _t(
        3,
        "Add calendar sync for FieldSync: Google Calendar for dispatchers and "
        "ICS export for technicians still on React.",
        "feature: calendar sync",
    ),
    _t(
        4,
        "FieldSync needs offline draft notes in the React client when coverage "
        "is poor, synced when the device is back online.",
        "feature: offline draft notes",
    ),
    _t(
        5,
        "Pivot: stop the React web client. FieldSync must ship as a Flutter "
        "mobile app for iOS and Android instead. Update the stack accordingly.",
        "stack includes Flutter",
    ),
    _t(
        6,
        "After the Flutter pivot, re-estimate push notifications and camera "
        "capture for FieldSync job completion on mobile devices.",
        "stack includes Flutter",
    ),
    _t(
        7,
        "FieldSync Flutter app still needs the FastAPI backend for scheduling. "
        "Confirm API contracts for the mobile clients.",
        "stack includes Flutter",
    ),
    _t(
        8,
        "Plan a cutover: deprecate the unfinished React screens and keep only "
        "Flutter for FieldSync technician workflows going forward.",
        "stack includes Flutter",
    ),
    _t(
        9,
        "Add biometric unlock on the Flutter FieldSync app for technicians who "
        "store customer site access codes on device.",
        "stack includes Flutter",
    ),
    _t(
        10,
        "Summarize FieldSync with Flutter as the client stack and list what "
        "React work can be discarded from the estimate.",
        "stack includes Flutter",
    ),
    # Extra turns so N=20 is available if budget allows.
    _t(
        11,
        "FieldSync Flutter deep links should open a specific job from SMS so "
        "dispatchers can nudge technicians quickly.",
        "stack includes Flutter",
    ),
    _t(
        12,
        "Add crash reporting for the Flutter FieldSync builds in staging and "
        "production with release symbols retained.",
        "stack includes Flutter",
    ),
    _t(
        13,
        "FieldSync needs background location pings from Flutter every five "
        "minutes while a job is in progress for ETA accuracy.",
        "stack includes Flutter",
    ),
    _t(
        14,
        "Estimate tablet layout tweaks for Flutter FieldSync used in vans with "
        "larger screens than phones.",
        "stack includes Flutter",
    ),
    _t(
        15,
        "Confirm FieldSync still targets Flutter only; do not revive React "
        "technician screens in this plan.",
        "stack includes Flutter",
    ),
    _t(
        16,
        "Add App Store and Play Store release checklist items for FieldSync "
        "Flutter, including screenshots and privacy text.",
        "stack includes Flutter",
    ),
    _t(
        17,
        "FieldSync Flutter offline queue should retry photo uploads with "
        "exponential backoff when connectivity returns.",
        "stack includes Flutter",
    ),
    _t(
        18,
        "Include accessibility labels for primary Flutter FieldSync actions: "
        "claim job, complete job, and call dispatcher.",
        "stack includes Flutter",
    ),
    _t(
        19,
        "Plan a dogfood week where internal staff run FieldSync Flutter on real "
        "jobs before external pilot customers.",
        "stack includes Flutter",
    ),
    _t(
        20,
        "Final FieldSync check: the remembered client stack must include "
        "Flutter, not React, for technician mobile work.",
        "stack includes Flutter",
    ),
)


# ---------------------------------------------------------------------------
# contradiction — budget 30k at turn 3, then 80k at turn 8
# ---------------------------------------------------------------------------
_CONTRADICTION: tuple[TurnSpec, ...] = (
    _t(
        1,
        "Estimate LedgerLite, a lightweight invoicing web app for freelancers "
        "who need quotes, invoices, and basic payment tracking.",
        "project name: LedgerLite",
    ),
    _t(
        2,
        "LedgerLite MVP: create invoice, send PDF by email, mark paid manually. "
        "Use a small team and keep scope tight.",
        "scope: invoice PDF email paid",
    ),
    _t(
        3,
        "Hard constraint for LedgerLite: the budget is locked at 30000 EUR for "
        "the whole MVP. Do not propose work beyond that ceiling.",
        "budget locked: 30000 EUR",
    ),
    _t(
        4,
        "Within the locked 30000 EUR LedgerLite budget, add Stripe checkout for "
        "card payments and a simple reconciliation view.",
        "budget locked: 30000 EUR",
    ),
    _t(
        5,
        "LedgerLite still under 30000 EUR: add client contact CRUD and tax rate "
        "presets for Spain and Germany.",
        "budget locked: 30000 EUR",
    ),
    _t(
        6,
        "Keep LedgerLite estimates honest against the 30000 EUR lock; prefer "
        "cutting nice-to-haves over expanding hours.",
        "budget locked: 30000 EUR",
    ),
    _t(
        7,
        "LedgerLite stakeholders ask for reminder emails before due dates. Fit "
        "that only if the 30000 EUR budget still holds.",
        "budget locked: 30000 EUR",
    ),
    _t(
        8,
        "Update: leadership now says the LedgerLite budget is 80000 EUR instead. "
        "Re-plan with the larger number, but note the earlier lock conflict.",
        "budget claimed: 80000 EUR",
    ),
    _t(
        9,
        "With the disputed LedgerLite budget (30k locked earlier vs 80k now), "
        "estimate multi-currency invoices and accountant CSV export.",
        "budget locked: 30000 EUR",
    ),
    _t(
        10,
        "Summarize LedgerLite: which budget figure should the plan honor, and "
        "what happens to scope if we keep the original 30000 EUR lock.",
        "budget locked: 30000 EUR",
    ),
    _t(
        11,
        "LedgerLite contradiction stress: restate that turn 3 locked 30000 EUR "
        "even though turn 8 floated 80000 EUR.",
        "budget locked: 30000 EUR",
    ),
    _t(
        12,
        "If LedgerLite honors 30000 EUR, list features that must stay out of "
        "MVP despite the later 80000 EUR claim.",
        "budget locked: 30000 EUR",
    ),
    _t(
        13,
        "LedgerLite finance wants a written assumption about the active budget "
        "number for change control.",
        "budget locked: 30000 EUR",
    ),
    _t(
        14,
        "Propose a phased LedgerLite path: MVP under 30000 EUR, then a paid "
        "phase-two only if 80000 EUR is formally approved.",
        "budget locked: 30000 EUR",
    ),
    _t(
        15,
        "Check LedgerLite memory: the locked budget fact from early turns should "
        "still read as 30000 EUR unless explicitly unlocked.",
        "budget locked: 30000 EUR",
    ),
    _t(
        16,
        "LedgerLite: do not silently replace 30000 EUR with 80000 EUR in the "
        "project assumptions without calling out the contradiction.",
        "budget locked: 30000 EUR",
    ),
    _t(
        17,
        "Estimate a cheap LedgerLite contingency buffer still framed under the "
        "original 30000 EUR lock.",
        "budget locked: 30000 EUR",
    ),
    _t(
        18,
        "LedgerLite stakeholders ask again which budget is canonical. Prefer "
        "the early lock of 30000 EUR for MemoryDrift checks.",
        "budget locked: 30000 EUR",
    ),
    _t(
        19,
        "Tighten LedgerLite wording so future turns can find the substring "
        "budget locked: 30000 EUR in metadata or summaries.",
        "budget locked: 30000 EUR",
    ),
    _t(
        20,
        "Final LedgerLite pass: confirm the remembered budget lock remains "
        "30000 EUR despite the turn-8 claim of 80000 EUR.",
        "budget locked: 30000 EUR",
    ),
)


_PROFILES: dict[ScenarioName, tuple[TurnSpec, ...]] = {
    "growing": _GROWING,
    "pivot": _PIVOT,
    "contradiction": _CONTRADICTION,
}


def get_profile(name: ScenarioName | str) -> tuple[TurnSpec, ...]:
    """Return the full turn script for a named profile.

    :arg name: One of ``growing``, ``pivot``, ``contradiction``.
    :return: Immutable sequence of turn specs (up to 20 turns).
    :raises KeyError: If ``name`` is not a known profile.
    """
    key = name.strip().lower()  # type: ignore[union-attr]
    if key not in _PROFILES:
        raise KeyError(
            f"Unknown scenario profile {name!r}; "
            f"expected one of {list(_PROFILES)}"
        )
    return _PROFILES[key]  # type: ignore[index]


def build_scenario(
    name: ScenarioName | str,
    n_turns: int,
) -> list[TurnSpec]:
    """Return the first ``n_turns`` of a profile (``N`` in the stress matrix).

    :arg name: Scenario profile id.
    :arg n_turns: How many turns to keep (typically 1, 3, 6, 10, or 20).
    :return: Truncated list of ``TurnSpec`` with stable 1-based indexes.
    :raises KeyError: If the profile name is unknown.
    :raises ValueError: If ``n_turns`` is out of range for the profile.
    """
    profile = get_profile(name)
    if n_turns < 1 or n_turns > len(profile):
        raise ValueError(
            f"n_turns must be in 1..{len(profile)} for {name!r}, got {n_turns}"
        )
    return list(profile[:n_turns])


def iter_scenario_matrix(
    *,
    scenarios: tuple[ScenarioName, ...] | list[ScenarioName] | None = None,
    n_values: tuple[int, ...] | list[int] | None = None,
) -> list[tuple[ScenarioName, int, list[TurnSpec]]]:
    """Expand scenario names × ``N`` into concrete turn lists.

    :arg scenarios: Profiles to include (default: all three).
    :arg n_values: Turn counts to truncate to (default: ``DEFAULT_N_TURNS``).
    :return: List of ``(name, n_turns, turns)`` ready for the runner.
    :raises KeyError: If a scenario name is unknown.
    :raises ValueError: If any ``n`` exceeds a profile length.
    """
    names = tuple(scenarios) if scenarios is not None else SCENARIO_NAMES
    lengths = tuple(n_values) if n_values is not None else DEFAULT_N_TURNS
    matrix: list[tuple[ScenarioName, int, list[TurnSpec]]] = []
    for name in names:
        resolved = name.strip().lower()  # type: ignore[union-attr]
        if resolved not in _PROFILES:
            raise KeyError(f"Unknown scenario profile {name!r}")
        typed = resolved  # type: ignore[assignment]
        for n in lengths:
            matrix.append((typed, n, build_scenario(typed, n)))
    return matrix
