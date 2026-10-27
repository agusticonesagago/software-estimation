"""Unit tests for static CAG estimation examples."""

import json

import pytest

from app.context import examples as examples_module
from app.context.examples import (
    CANONICAL_EXAMPLES,
    format_examples_for_prompt,
    load_cag_examples_markdown,
    select_examples,
)
from app.services.prompts import build_system_instructions, build_system_prompt


def test_canonical_examples_are_present() -> None:
    """Ship at least two canonical examples with required fields.

    :return: None.
    :raises AssertionError: If examples are missing or incomplete.
    """
    assert len(CANONICAL_EXAMPLES) >= 2
    for example in CANONICAL_EXAMPLES:
        assert example.title.strip()
        assert example.meeting_summary.strip()
        assert example.estimation_markdown.strip()
        assert example.breakdown
        assert example.total_hours > 0
        assert example.total_cost > 0
        assert example.team
        assert example.duration_weeks > 0


def test_select_examples_caps_at_pool_size() -> None:
    """Cap selected examples at the available pool.

    :return: None.
    :raises AssertionError: If slicing is wrong.
    """
    assert select_examples(2) == CANONICAL_EXAMPLES[:2]
    assert select_examples(999) == CANONICAL_EXAMPLES
    assert select_examples(0) == []


def test_format_examples_markdown_and_json() -> None:
    """Render markdown and JSON prompt formats from structured data.

    :return: None.
    :raises AssertionError: If rendered output is incomplete.
    """
    sample = select_examples(1)
    md = format_examples_for_prompt(sample, "markdown")
    assert "--- EXAMPLE 1 ---" in md
    assert sample[0].meeting_summary[:40] in md
    assert sample[0].title in md

    raw = format_examples_for_prompt(sample, "json")
    assert "Reference examples (JSON):" in raw
    payload = json.loads(raw.split("\n", 1)[1])
    assert payload[0]["title"] == sample[0].title
    assert payload[0]["totals"]["hours"] == sample[0].total_hours


def test_format_examples_narrative_and_unknown() -> None:
    """Render narrative format and reject unknown formats.

    :return: None.
    :raises AssertionError: If narrative/unknown handling is wrong.
    """
    sample = select_examples(1)
    narrative = format_examples_for_prompt(sample, "narrative")
    assert sample[0].title in narrative
    assert str(sample[0].total_hours) in narrative
    with pytest.raises(ValueError, match="Unknown example format"):
        format_examples_for_prompt(sample, "yaml")  # type: ignore[arg-type]


def test_load_cag_examples_requires_at_least_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject fewer than two few-shot examples.

    :arg monkeypatch: Pytest monkeypatch fixture.
    :return: None.
    :raises AssertionError: If ``ValueError`` is not raised.
    """
    monkeypatch.setattr(examples_module, "CANONICAL_EXAMPLES", [])
    with pytest.raises(ValueError, match="at least two"):
        examples_module.load_cag_examples_markdown()


def test_cag_markdown_has_clear_separators() -> None:
    """Wrap examples with CAG static-context and EXAMPLE markers.

    :return: None.
    :raises AssertionError: If required markers are missing.
    """
    text = load_cag_examples_markdown()
    assert "CAG STATIC CONTEXT" in text
    assert "--- EXAMPLE 1 ---" in text
    assert "Meeting Summary:" in text
    assert "END CAG STATIC CONTEXT" in text


def test_system_instructions_exclude_cag_examples() -> None:
    """Expose intro + validations without few-shot example bodies.

    :return: None.
    :raises AssertionError: If CAG example markers leak into instructions.
    """
    text = build_system_instructions()
    assert "You are an expert software estimator" in text
    assert "Final validations" in text
    assert "CAG STATIC CONTEXT" not in text


def test_system_prompt_includes_cag_context() -> None:
    """Inject CAG examples into the system prompt.

    :return: None.
    :raises AssertionError: If the prompt is missing CAG content.
    """
    prompt = build_system_prompt()
    assert "You are an expert software estimator" in prompt
    assert "--- EXAMPLE 1 ---" in prompt
    assert CANONICAL_EXAMPLES[0].meeting_summary[:40] in prompt


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
