"""LLM service: provider-agnostic calls via LiteLLM."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from litellm import completion

from app.config import LLMProvider, Settings, get_settings
from app.schemas.llm import LLMResult

# Deterministic answers: stay close to prompt examples, less invention.
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 4096


class LLMService:
    """Generate software estimations through the configured LLM provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Create a service bound to application settings.

        :arg settings: Optional settings override; defaults to ``get_settings()``.
        :return: None.
        :raises ValidationError: If default settings fail to load.
        """
        self.settings = settings or get_settings()
        self.last_prompt_tokens: int | None = None
        self.last_completion_tokens: int | None = None

    def generate(self, system: str, user: str) -> LLMResult:
        """Generate an estimation from separate system and user messages.

        :arg system: Rendered system prompt (instructions + examples).
        :arg user: Rendered user prompt (project description wrapper).
        :return: Provider-normalized free-text estimation result.
        :raises ValueError: If ``LLM_PROVIDER`` is unsupported or the API key is missing.
        :raises Exception: Propagates provider/network errors from LiteLLM.
        """
        provider = self._resolve_provider()
        model = self.settings.resolved_model
        response = completion(
            **self._completion_kwargs(system=system, user=user, stream=False)
        )
        content = (response.choices[0].message.content or "").strip()
        usage = getattr(response, "usage", None)
        prompt_tokens, completion_tokens = self._usage_tokens(usage)
        self.last_prompt_tokens = prompt_tokens
        self.last_completion_tokens = completion_tokens
        return LLMResult(
            estimation=content,
            model=model,
            provider=provider.value,
            confidence=0.0,
            confidence_rationale="",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def generate_stream(self, system: str, user: str) -> Iterator[str]:
        """Stream estimation tokens from LiteLLM using separate system/user roles.

        Token usage (when the provider reports it) is stored on
        ``last_prompt_tokens`` / ``last_completion_tokens`` after the stream ends.

        :arg system: Rendered system prompt.
        :arg user: Rendered user prompt.
        :return: Iterator of non-empty text deltas.
        :raises ValueError: If ``LLM_PROVIDER`` is unsupported or the API key is missing.
        :raises Exception: Propagates provider/network errors from LiteLLM.
        """
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        stream = completion(
            **self._completion_kwargs(system=system, user=user, stream=True)
        )
        for chunk in stream:
            prompt_tokens, completion_tokens = self._usage_tokens(
                getattr(chunk, "usage", None)
            )
            if prompt_tokens is not None:
                self.last_prompt_tokens = prompt_tokens
            if completion_tokens is not None:
                self.last_completion_tokens = completion_tokens
            text = self._chunk_text(chunk)
            if text:
                yield text

    def _completion_kwargs(
        self, *, system: str, user: str, stream: bool
    ) -> dict[str, Any]:
        """Build shared LiteLLM ``completion`` keyword arguments.

        :arg system: System-role message content.
        :arg user: User-role message content.
        :arg stream: Whether to request a streaming response.
        :return: Keyword arguments for ``litellm.completion``.
        :raises ValueError: If the provider or API key is invalid.
        """
        provider = self._resolve_provider()
        kwargs: dict[str, Any] = {
            "model": self.settings.litellm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
            "api_key": self._api_key_for_provider(provider),
            "stream": stream,
        }
        if stream:
            # OpenAI-compatible: ask for usage on the final stream chunk.
            kwargs["stream_options"] = {"include_usage": True}
        return kwargs

    @staticmethod
    def _usage_tokens(usage: Any) -> tuple[int | None, int | None]:
        """Read prompt/completion token counts from a usage object or mapping.

        :arg usage: Provider usage payload (or ``None``).
        :return: ``(prompt_tokens, completion_tokens)``.
        :raises: Does not raise under normal operation.
        """
        if usage is None:
            return None, None
        if isinstance(usage, dict):
            return usage.get("prompt_tokens"), usage.get("completion_tokens")
        return (
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
        )

    @staticmethod
    def _chunk_text(chunk: Any) -> str:
        """Extract text delta from a LiteLLM/OpenAI-style stream chunk.

        :arg chunk: Streaming chunk object or mapping.
        :return: Delta content string, or empty if none.
        :raises: Does not raise under normal operation.
        """
        choices = getattr(chunk, "choices", None)
        if choices is None and isinstance(chunk, dict):
            choices = chunk.get("choices")
        if not choices:
            return ""
        first = choices[0]
        delta = getattr(first, "delta", None)
        if delta is None and isinstance(first, dict):
            delta = first.get("delta") or {}
            content = delta.get("content") if isinstance(delta, dict) else None
            return content or ""
        content = getattr(delta, "content", None) if delta is not None else None
        return content or ""

    def _resolve_provider(self) -> LLMProvider:
        """Normalize settings provider into ``LLMProvider``.

        :return: Supported provider enum member.
        :raises ValueError: If the configured provider is not supported.
        """
        raw = self.settings.llm_provider
        if isinstance(raw, LLMProvider):
            return raw
        try:
            return LLMProvider(str(raw))
        except ValueError as exc:
            raise ValueError(f"Unsupported LLM provider: {raw}") from exc

    def _api_key_for_provider(self, provider: LLMProvider) -> str:
        """Return the API key for the given provider.

        :arg provider: Active LLM provider.
        :return: Non-empty API key string for LiteLLM.
        :raises ValueError: If the provider API key is missing.
        """
        key = (
            self.settings.openai_api_key
            if provider is LLMProvider.OPENAI
            else self.settings.anthropic_api_key
        )
        if not key:
            raise ValueError(f"Missing API key for LLM provider: {provider.value}")
        return key


def generate_estimation(system: str, user: str) -> LLMResult:
    """Convenience wrapper around ``LLMService.generate``.

    :arg system: Rendered system prompt.
    :arg user: Rendered user prompt.
    :return: Provider-normalized free-text estimation result.
    :raises ValueError: If ``LLM_PROVIDER`` is unsupported or the API key is missing.
    :raises Exception: Propagates provider/network errors from LiteLLM.
    """
    return LLMService().generate(system, user)


def stream_estimation(system: str, user: str) -> Iterator[str]:
    """Convenience wrapper around ``LLMService.generate_stream``.

    :arg system: Rendered system prompt.
    :arg user: Rendered user prompt.
    :return: Iterator of text deltas from the model.
    :raises ValueError: If ``LLM_PROVIDER`` is unsupported or the API key is missing.
    :raises Exception: Propagates provider/network errors from LiteLLM.
    """
    return LLMService().generate_stream(system, user)
