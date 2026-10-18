"""Unit tests for static CAG estimation examples."""

import pytest

from app.context import examples as examples_module
from app.context.examples import ESTIMATION_EXAMPLES, load_cag_examples_markdown
from app.services.prompts import build_system_prompt


def test_estimation_examples_are_present() -> None:
    """Ship at least two CAG few-shot examples with required keys.

    :return: None.
    :raises AssertionError: If examples are missing or incomplete.
    """
    assert len(ESTIMATION_EXAMPLES) >= 2
    for example in ESTIMATION_EXAMPLES:
        assert example["meeting_summary"].strip()
        assert example["estimation"].strip()


def test_load_cag_examples_requires_at_least_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject fewer than two few-shot examples.

    :arg monkeypatch: Pytest monkeypatch fixture.
    :return: None.
    :raises AssertionError: If ``ValueError`` is not raised.
    """
    monkeypatch.setattr(examples_module, "ESTIMATION_EXAMPLES", [])
    with pytest.raises(ValueError, match="at least two"):
        examples_module.load_cag_examples_markdown()


def test_cag_markdown_has_clear_separators() -> None:
    """Wrap examples with explicit CAG begin/end markers.

    :return: None.
    :raises AssertionError: If required markers are missing.
    """
    text = load_cag_examples_markdown()
    assert "CAG STATIC CONTEXT" in text
    assert "CAG FEW-SHOT EXAMPLE 1/" in text
    assert "END CAG FEW-SHOT EXAMPLE 1/" in text
    assert "END CAG STATIC CONTEXT" in text
    assert "Meeting summary" in text


def test_system_prompt_includes_cag_context() -> None:
    """Inject CAG examples into the system prompt.

    :return: None.
    :raises AssertionError: If the prompt is missing CAG content.
    """
    prompt = build_system_prompt()
    assert "You are an expert software estimator" in prompt
    assert "CAG FEW-SHOT EXAMPLE" in prompt
    assert ESTIMATION_EXAMPLES[0]["meeting_summary"][:40] in prompt


def test_system_prompt_order_is_intro_examples_then_validations() -> None:
    """Keep prompt order: intro → CAG examples → final validations.

    :return: None.
    :raises AssertionError: If section order is wrong.
    """
    prompt = build_system_prompt()
    intro_at = prompt.index("You are an expert software estimator")
    examples_at = prompt.index("CAG STATIC CONTEXT")
    validations_at = prompt.index("Final validations (apply last")
    assert intro_at < examples_at < validations_at
    assert '"confidence"' in prompt
