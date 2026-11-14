"""Unit tests for CAG stress metrics (pass / fail / boundary)."""

import pytest

from app.schemas.session import TurnObserved
from app.services.sessions import ProjectMetadata
from evals.stress.metrics import (
    AttachmentRecallMetric,
    CostBudgetMetric,
    LatencyBudgetMetric,
    MemoryDriftMetric,
    MetricResult,
)


def _observation(**overrides: object) -> dict[str, object]:
    """Build a minimal turn_observed-like dict.

    :arg overrides: Fields to overwrite.
    :return: Observation mapping.
    :raises: Does not raise under normal operation.
    """
    base: dict[str, object] = {
        "turn_index": 1,
        "session_id": "sess-1",
        "enriched_transcript_chars": 100,
        "attachments_total_chars": 0,
        "messages_in_window": 3,
        "anchors_count": 0,
        "summary_chars": 0,
        "tokens_in": 10,
        "tokens_out": 5,
        "cost_usd": 0.001,
        "latency_ms": 500.0,
        "cache_hit_kind": "none",
        "last_resolved_tier": None,
    }
    base.update(overrides)
    return base


def test_latency_budget_pass_fail_and_boundary() -> None:
    """Latency metric passes under/equal budget and fails above / missing.

    :return: None.
    :raises AssertionError: If pass/fail/boundary behaviour is wrong.
    """
    metric = LatencyBudgetMetric(budget_ms=1000)
    ok = metric.evaluate(_observation(latency_ms=800))
    assert ok == MetricResult(
        name="latency_budget",
        score=1.0,
        passed=True,
        details=ok.details,
    )
    assert ok.passed is True

    boundary = metric.evaluate(_observation(latency_ms=1000))
    assert boundary.passed is True
    assert boundary.score == 1.0

    fail = metric.evaluate(_observation(latency_ms=1000.1))
    assert fail.passed is False
    assert fail.score == 0.0

    missing = metric.evaluate(_observation(latency_ms=None))
    assert missing.passed is False


def test_cost_budget_pass_fail_and_boundary() -> None:
    """Cost metric passes under/equal budget and fails above / missing.

    :return: None.
    :raises AssertionError: If pass/fail/boundary behaviour is wrong.
    """
    metric = CostBudgetMetric(budget_usd=0.01)
    assert metric.evaluate(_observation(cost_usd=0.005)).passed is True
    assert metric.evaluate(_observation(cost_usd=0.01)).passed is True
    assert metric.evaluate(_observation(cost_usd=0.0100001)).passed is False
    assert metric.evaluate(_observation(cost_usd=None)).passed is False


def test_latency_and_cost_accept_turn_observed_model() -> None:
    """Budget metrics accept the Pydantic ``TurnObserved`` model.

    :return: None.
    :raises AssertionError: If model evaluation fails.
    """
    observed = TurnObserved.model_validate(_observation(latency_ms=10, cost_usd=0.0))
    assert LatencyBudgetMetric(50).evaluate(observed).passed is True
    assert CostBudgetMetric(0.0).evaluate(observed).passed is True


def test_memory_drift_finds_fact_in_metadata() -> None:
    """MemoryDrift matches labeled project-name facts in metadata.

    :return: None.
    :raises AssertionError: If a present fact is scored as missing.
    """
    snapshot = {
        "session_id": "s1",
        "project_metadata": ProjectMetadata(
            project_name="Nimbus",
            mentioned_technologies=["React"],
        ),
        "summary": None,
        "anchors": [],
    }
    metric = MemoryDriftMetric("project name: Nimbus")
    result = metric.evaluate(snapshot)
    assert result.passed is True
    assert result.score == 1.0


def test_memory_drift_fails_when_fact_absent() -> None:
    """MemoryDrift fails when the fact is not in any selected store.

    :return: None.
    :raises AssertionError: If a missing fact is scored as present.
    """
    snapshot = {
        "project_metadata": {"project_name": "Other", "mentioned_technologies": []},
        "summary": "",
        "anchors": [],
    }
    result = MemoryDriftMetric("project name: Nimbus").evaluate(snapshot)
    assert result.passed is False
    assert result.score == 0.0


def test_memory_drift_summary_anchors_empty_baseline() -> None:
    """Restricting where=summary/anchors fails on this empty baseline.

    :return: None.
    :raises AssertionError: If empty stores incorrectly pass.
    """
    snapshot = {
        "project_metadata": ProjectMetadata(project_name="Nimbus"),
        "summary": "",
        "anchors": [],
    }
    only_summary = MemoryDriftMetric(
        "project name: Nimbus",
        where=["summary", "anchors"],
    ).evaluate(snapshot)
    assert only_summary.passed is False

    metadata_only = MemoryDriftMetric(
        "stack includes Flutter",
        where=["metadata"],
    ).evaluate(
        {
            "project_metadata": {
                "project_name": "FieldSync",
                "mentioned_technologies": ["Flutter"],
            }
        }
    )
    assert metadata_only.passed is True


def test_memory_drift_is_case_insensitive() -> None:
    """Fact matching ignores case.

    :return: None.
    :raises AssertionError: If case differences change the score.
    """
    snapshot = {
        "project_metadata": {
            "agreed_scope": "Budget locked: 30000 EUR for MVP",
            "mentioned_technologies": [],
        }
    }
    assert (
        MemoryDriftMetric("budget locked: 30000 EUR", where=["metadata"])
        .evaluate(snapshot)
        .passed
        is True
    )


def test_metric_constructors_reject_invalid_args() -> None:
    """Constructors validate budgets, facts, and where stores.

    :return: None.
    :raises AssertionError: If invalid input is accepted.
    """
    with pytest.raises(ValueError):
        LatencyBudgetMetric(-1)
    with pytest.raises(ValueError):
        CostBudgetMetric(-0.01)
    with pytest.raises(ValueError):
        MemoryDriftMetric("  ")
    with pytest.raises(ValueError):
        MemoryDriftMetric("x", where=["vector_db"])
    with pytest.raises(ValueError):
        AttachmentRecallMetric(" ")


def test_attachment_recall_pass_and_fail() -> None:
    """Attachment recall finds markers in estimate text.

    :return: None.
    :raises AssertionError: If marker detection is wrong.
    """
    metric = AttachmentRecallMetric("STRESS_ATTACHMENT_MARKER_5KB")
    assert metric.evaluate("... STRESS_ATTACHMENT_MARKER_5KB mentioned ...").passed
    assert metric.evaluate("no marker here").passed is False
    assert metric.evaluate(None).passed is False
