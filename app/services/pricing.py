"""Simple USD pricing table for stress-test cost observations.

Prices are approximate list rates (USD per 1M tokens) used only for
``turn_observed.cost_usd`` and budget metrics — not for billing.
"""

from __future__ import annotations

# model_id (without provider prefix) -> (input_usd_per_1m, output_usd_per_1m)
_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-haiku-4-5": (0.80, 4.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-5": (3.00, 15.00),
}

_DEFAULT_COSTS = (0.15, 0.60)


def estimate_cost_usd(
    model: str,
    *,
    tokens_in: int | None,
    tokens_out: int | None,
) -> float:
    """Estimate USD cost for a single completion from token counts.

    :arg model: Model id (with or without ``provider/`` prefix).
    :arg tokens_in: Prompt / input tokens (``None`` treated as 0).
    :arg tokens_out: Completion / output tokens (``None`` treated as 0).
    :return: Estimated cost in USD (non-negative).
    :raises: Does not raise under normal operation.
    """
    bare = model.split("/", 1)[-1].strip().lower()
    input_rate, output_rate = _MODEL_COSTS.get(bare, _DEFAULT_COSTS)
    # Also try exact key without lowercasing for dated Anthropic ids.
    if bare not in _MODEL_COSTS:
        for key, rates in _MODEL_COSTS.items():
            if key.lower() == bare:
                input_rate, output_rate = rates
                break
    tin = max(0, int(tokens_in or 0))
    tout = max(0, int(tokens_out or 0))
    return (tin / 1_000_000.0) * input_rate + (tout / 1_000_000.0) * output_rate
