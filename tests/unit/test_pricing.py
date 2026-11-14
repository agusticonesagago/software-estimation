"""Unit tests for the simple LLM pricing table."""

import pytest

from app.services.pricing import estimate_cost_usd


def test_estimate_cost_usd_gpt4o_mini() -> None:
    """Price gpt-4o-mini tokens with the published table rates.

    :return: None.
    :raises AssertionError: If the USD estimate is wrong.
    """
    cost = estimate_cost_usd("gpt-4o-mini", tokens_in=1_000_000, tokens_out=1_000_000)
    assert cost == pytest.approx(0.75)


def test_estimate_cost_usd_handles_provider_prefix_and_none_tokens() -> None:
    """Strip provider prefixes and treat missing tokens as zero.

    :return: None.
    :raises AssertionError: If zero-token cost is non-zero.
    """
    assert estimate_cost_usd("openai/gpt-4o-mini", tokens_in=None, tokens_out=None) == 0.0


def test_estimate_cost_usd_unknown_model_uses_default_rates() -> None:
    """Fall back to default rates for unknown model ids.

    :return: None.
    :raises AssertionError: If the default pricing is not applied.
    """
    cost = estimate_cost_usd("mystery-model", tokens_in=1_000_000, tokens_out=0)
    assert cost == pytest.approx(0.15)
