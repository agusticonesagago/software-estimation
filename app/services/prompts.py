"""CAG system-prompt builders (separated from LLM provider I/O)."""

from __future__ import annotations

from app.context.examples import load_cag_examples_markdown

SYSTEM_PROMPT_INTRO = """You are an expert software estimator.
Given a client meeting transcription, produce a clear, actionable estimation
in Markdown, plus a numeric confidence score.

Your estimation Markdown should cover:
- Title / scope summary
- Task breakdown (table with hours and role)
- Suggested team
- Totals (hours, duration, rough cost when relevant)
- Risks or important assumptions

Below are prior estimation examples (CAG static context). Use them as
style and structure references for the Markdown estimation only.
"""

SYSTEM_PROMPT_VALIDATIONS = """
## Final validations (apply last, after studying the examples)

Before you answer, validate all of the following:

1. Scope stays faithful to the transcription — do not invent a much larger project.
2. Estimation Markdown language matches the transcription language.
3. Required sections are present: title/scope, task table (hours + role), team,
   totals, and risks/assumptions.
4. Hours, duration, and team size are consistent with each other.
5. CAG examples are references only — do not copy an example verbatim unless the
   new request is essentially identical.
6. Respect ``--- EXAMPLE N ---`` delimiters; do not mix scopes across example
   blocks.
7. Prefer explicit assumptions over silent guesses when information is missing.
8. Confidence must reflect uncertainty: lower when requirements are vague,
   missing constraints, or high risk; higher when scope, timeline, and stack
   are clear.

## Required response format (mandatory)

Respond with a single JSON object only (no markdown fences, no prose outside JSON):

{
  "estimation": "<Markdown estimation string>",
  "confidence": <number between 0.0 and 1.0>,
  "confidence_rationale": "<short explanation of the confidence score>"
}

`confidence` is how sure you are about this estimate (1.0 = very sure, 0.0 = guess).
"""


def build_system_instructions() -> str:
    """Build role + validation instructions without CAG few-shot examples.

    Useful for UI panels that show the active system rules separately from
    the static estimation examples.

    :return: Intro and validations concatenated.
    :raises: Does not raise under normal operation.
    """
    return (
        f"{SYSTEM_PROMPT_INTRO.strip()}\n\n"
        f"{SYSTEM_PROMPT_VALIDATIONS.strip()}\n"
    )


def build_system_prompt() -> str:
    """Build the system prompt: intro, then CAG examples, then validations.

    Order matters for CAG: role/intro first, few-shots next, hard checks last
    so constraints stay salient at the end of the context.

    :return: System prompt string ready for the LLM provider.
    :raises ValueError: If fewer than two CAG examples are defined.
    """
    return (
        f"{SYSTEM_PROMPT_INTRO.strip()}\n\n"
        f"{load_cag_examples_markdown().strip()}\n\n"
        f"{SYSTEM_PROMPT_VALIDATIONS.strip()}\n"
    )


__all__ = [
    "SYSTEM_PROMPT_INTRO",
    "SYSTEM_PROMPT_VALIDATIONS",
    "build_system_instructions",
    "build_system_prompt",
]
