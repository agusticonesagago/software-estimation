"""Deterministic stress metrics for CAG turn observations and session snapshots.

Lives under ``evals/stress/`` (not a legacy ``evals/metrics.py``) because the
inputs are ``turn_observed`` / session-snapshot shapes from this baseline, not
an ``EstimationResult`` framework.

``summary`` / ``anchors`` are always empty in the current CAG baseline: when
``MemoryDriftMetric`` is restricted to those stores it will fail (or report
empty haystack). Prefer including ``metadata`` until summarizer/anchors land.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class MetricResult:
    """Binary metric outcome with a 1.0 / 0.0 score.

    :ivar name: Metric identifier (stable for CSV columns).
    :ivar score: ``1.0`` if passed, otherwise ``0.0``.
    :ivar passed: Convenience mirror of ``score == 1.0``.
    :ivar details: Human-readable explanation for REPORT / debugging.
    """

    name: str
    score: float
    passed: bool
    details: str


def _as_mapping(value: Any) -> Mapping[str, Any]:
    """Normalize Pydantic models / objects / dicts to a mapping.

    :arg value: Observation or snapshot-like input.
    :return: Mapping of field name → value.
    :raises TypeError: If ``value`` cannot be converted.
    """
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dumped
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    raise TypeError(f"Unsupported observation/snapshot type: {type(value)!r}")


def _get_float(data: Mapping[str, Any], key: str) -> float | None:
    """Read an optional float field.

    :arg data: Mapping view of the observation.
    :arg key: Field name.
    :return: Parsed float, or ``None`` when missing/invalid.
    :raises: Does not raise under normal operation.
    """
    raw = data.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class LatencyBudgetMetric:
    """Pass when ``latency_ms`` is present and ``<= budget_ms``."""

    name = "latency_budget"

    def __init__(self, budget_ms: float) -> None:
        """Configure the latency ceiling.

        :arg budget_ms: Maximum accepted latency in milliseconds.
        :return: None.
        :raises ValueError: If ``budget_ms`` is negative.
        """
        if budget_ms < 0:
            raise ValueError(f"budget_ms must be >= 0, got {budget_ms}")
        self.budget_ms = float(budget_ms)

    def evaluate(self, observation: Any) -> MetricResult:
        """Score one ``turn_observed`` for latency budget.

        :arg observation: Mapping or model with ``latency_ms``.
        :return: ``MetricResult`` with score 1.0 or 0.0.
        :raises TypeError: If ``observation`` is not mapping-like.
        """
        data = _as_mapping(observation)
        latency = _get_float(data, "latency_ms")
        if latency is None:
            return MetricResult(
                name=self.name,
                score=0.0,
                passed=False,
                details="latency_ms missing; cannot evaluate budget",
            )
        passed = latency <= self.budget_ms
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            details=(
                f"latency_ms={latency} budget_ms={self.budget_ms} "
                f"({'ok' if passed else 'over budget'})"
            ),
        )


class CostBudgetMetric:
    """Pass when ``cost_usd`` is present and ``<= budget_usd``."""

    name = "cost_budget"

    def __init__(self, budget_usd: float) -> None:
        """Configure the cost ceiling.

        :arg budget_usd: Maximum accepted estimated USD cost.
        :return: None.
        :raises ValueError: If ``budget_usd`` is negative.
        """
        if budget_usd < 0:
            raise ValueError(f"budget_usd must be >= 0, got {budget_usd}")
        self.budget_usd = float(budget_usd)

    def evaluate(self, observation: Any) -> MetricResult:
        """Score one ``turn_observed`` for cost budget.

        :arg observation: Mapping or model with ``cost_usd``.
        :return: ``MetricResult`` with score 1.0 or 0.0.
        :raises TypeError: If ``observation`` is not mapping-like.
        """
        data = _as_mapping(observation)
        cost = _get_float(data, "cost_usd")
        if cost is None:
            return MetricResult(
                name=self.name,
                score=0.0,
                passed=False,
                details="cost_usd missing; cannot evaluate budget",
            )
        passed = cost <= self.budget_usd
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            details=(
                f"cost_usd={cost} budget_usd={self.budget_usd} "
                f"({'ok' if passed else 'over budget'})"
            ),
        )


def _normalize_haystack(parts: Iterable[str]) -> str:
    """Join haystack fragments and lowercase for case-insensitive match.

    :arg parts: Text fragments to concatenate.
    :return: Lowercased searchable string.
    :raises: Does not raise under normal operation.
    """
    return " ".join(part for part in parts if part).lower()


def _metadata_haystack(metadata: Any) -> list[str]:
    """Build searchable phrases from ``ProjectMetadata`` (dict or model).

    Includes labeled lines aligned with scenario ``fact_to_remember`` strings
    (e.g. ``project name: Nimbus``, ``stack includes Flutter``).

    :arg metadata: Session ``project_metadata`` payload.
    :return: List of text fragments.
    :raises: Does not raise under normal operation.
    """
    if metadata is None:
        return []
    data = _as_mapping(metadata)
    parts: list[str] = []
    project_name = data.get("project_name")
    if project_name:
        parts.append(str(project_name))
        parts.append(f"project name: {project_name}")
    team = data.get("assumed_team_size")
    if team is not None:
        parts.append(f"assumed_team_size: {team}")
        parts.append(f"team of {team}")
    techs = data.get("mentioned_technologies") or []
    if isinstance(techs, Sequence) and not isinstance(techs, (str, bytes)):
        for tech in techs:
            parts.append(str(tech))
            parts.append(f"stack includes {tech}")
        if techs:
            parts.append("stack includes " + ", ".join(str(t) for t in techs))
    scope = data.get("agreed_scope")
    if scope:
        parts.append(str(scope))
    # Raw dump helps facts that already appear verbatim in scope text.
    parts.append(" ".join(f"{key}: {value}" for key, value in data.items()))
    return parts


def _summary_haystack(snapshot: Mapping[str, Any]) -> list[str]:
    """Extract summary text from a snapshot (empty in this baseline).

    :arg snapshot: Session snapshot mapping.
    :return: Fragments (often empty).
    :raises: Does not raise under normal operation.
    """
    summary = snapshot.get("summary")
    if summary is None:
        return []
    if isinstance(summary, str):
        return [summary] if summary.strip() else []
    return [str(summary)]


def _anchors_haystack(snapshot: Mapping[str, Any]) -> list[str]:
    """Extract anchor texts from a snapshot (empty in this baseline).

    :arg snapshot: Session snapshot mapping.
    :return: Fragments (often empty).
    :raises: Does not raise under normal operation.
    """
    anchors = snapshot.get("anchors")
    if not anchors:
        # Also accept anchors_count-only snapshots: nothing to search.
        return []
    if isinstance(anchors, str):
        return [anchors]
    if isinstance(anchors, Sequence):
        parts: list[str] = []
        for item in anchors:
            if isinstance(item, Mapping):
                text = item.get("text") or item.get("content") or item.get("value")
                parts.append(str(text if text is not None else item))
            else:
                parts.append(str(item))
        return parts
    return [str(anchors)]


class MemoryDriftMetric:
    """Pass when ``fact`` appears (case-insensitive) in selected snapshot stores.

    Default ``where`` is ``summary``, ``anchors``, and ``metadata``. In this
    repo summary/anchors are absent, so effective recall is metadata-only unless
    the runner injects those fields later.
    """

    name = "memory_drift"

    def __init__(
        self,
        fact: str,
        where: Sequence[str] | None = None,
    ) -> None:
        """Configure the fact needle and search stores.

        :arg fact: Claim that later turns should still retain.
        :arg where: Stores to search (subset of summary/anchors/metadata).
        :return: None.
        :raises ValueError: If ``fact`` is blank or ``where`` has unknown keys.
        """
        cleaned = fact.strip()
        if not cleaned:
            raise ValueError("fact must be a non-empty string")
        stores = list(where) if where is not None else ["summary", "anchors", "metadata"]
        allowed = {"summary", "anchors", "metadata"}
        unknown = set(stores) - allowed
        if unknown:
            raise ValueError(f"Unsupported where entries: {sorted(unknown)}")
        if not stores:
            raise ValueError("where must contain at least one store")
        self.fact = cleaned
        self.where: list[str] = stores

    def evaluate(self, session_snapshot: Any) -> MetricResult:
        """Score whether ``fact`` is still present in the session snapshot.

        :arg session_snapshot: GET ``/sessions/{id}`` body or equivalent.
        :return: ``MetricResult`` with score 1.0 or 0.0.
        :raises TypeError: If ``session_snapshot`` is not mapping-like.
        """
        snapshot = _as_mapping(session_snapshot)
        fragments: list[str] = []
        searched: list[str] = []
        for store in self.where:
            if store == "summary":
                parts = _summary_haystack(snapshot)
            elif store == "anchors":
                parts = _anchors_haystack(snapshot)
            else:
                meta = snapshot.get("project_metadata", snapshot.get("metadata"))
                parts = _metadata_haystack(meta)
            if parts:
                fragments.extend(parts)
                searched.append(store)
            else:
                searched.append(f"{store}:empty")

        haystack = _normalize_haystack(fragments)
        needle = self.fact.lower()
        found = bool(haystack) and needle in haystack
        return MetricResult(
            name=self.name,
            score=1.0 if found else 0.0,
            passed=found,
            details=(
                f"fact={self.fact!r} found={found} "
                f"where={self.where} searched={searched}"
            ),
        )


@dataclass
class AttachmentRecallMetric:
    """Pass when an attachment marker appears in the estimate response text.

    Used for the attachment-size stress curve (not one of the three core
    budget/drift metrics, but needed for recall vs KB). Kept here so the
    runner can import a single metrics module.
    """

    marker: str
    name: str = field(default="attachment_recall", init=False)

    def __post_init__(self) -> None:
        """Validate the marker needle.

        :return: None.
        :raises ValueError: If ``marker`` is blank.
        """
        cleaned = self.marker.strip()
        if not cleaned:
            raise ValueError("marker must be a non-empty string")
        object.__setattr__(self, "marker", cleaned)

    def evaluate(self, response_text: str | None) -> MetricResult:
        """Score marker recall inside free-text estimation output.

        :arg response_text: ``SessionEstimateResponse.text`` (or similar).
        :return: ``MetricResult`` with score 1.0 or 0.0.
        :raises: Does not raise under normal operation.
        """
        text = response_text or ""
        found = self.marker.lower() in text.lower()
        return MetricResult(
            name=self.name,
            score=1.0 if found else 0.0,
            passed=found,
            details=f"marker={self.marker!r} found={found} chars={len(text)}",
        )
