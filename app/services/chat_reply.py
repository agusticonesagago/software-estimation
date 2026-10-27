"""Helpers to format LLM estimation results for the Streamlit chat UI."""

from __future__ import annotations

from app.schemas.llm import LLMResult, parse_llm_estimation_payload


def format_estimation_reply(result: LLMResult) -> str:
    """Build the assistant Markdown shown in the Streamlit chat.

    :arg result: Normalized LLM estimation result.
    :return: Markdown string with estimation body and short metadata footer.
    :raises: Does not raise under normal operation.
    """
    footer = (
        f"\n\n---\n"
        f"_Confidence: {result.confidence:.2f}_"
        f" — {result.confidence_rationale}\n"
        f"_Model: {result.provider}/{result.model}_"
    )
    return f"{result.estimation.strip()}{footer}"


def format_reply_from_raw_payload(
    raw: str,
    *,
    model: str,
    provider: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> str:
    """Parse streamed/complete JSON payload into chat Markdown.

    Falls back to the raw model text when JSON parsing fails (partial stream).

    :arg raw: Full model text (JSON object expected).
    :arg model: Model id for the footer.
    :arg provider: Provider name for the footer.
    :arg prompt_tokens: Optional prompt token count.
    :arg completion_tokens: Optional completion token count.
    :return: Formatted assistant Markdown, or ``raw`` if parsing fails.
    :raises: Does not raise under normal operation.
    """
    try:
        payload = parse_llm_estimation_payload(raw)
    except ValueError:
        return raw
    result = LLMResult(
        estimation=payload.estimation,
        model=model,
        provider=provider,
        confidence=payload.confidence,
        confidence_rationale=payload.confidence_rationale,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    return format_estimation_reply(result)


__all__ = ["format_estimation_reply", "format_reply_from_raw_payload"]
