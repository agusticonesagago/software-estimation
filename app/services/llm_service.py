"""LLM service: provider-agnostic calls via LiteLLM with a CAG system prompt."""

from __future__ import annotations

from litellm import completion

from app.config import LLMProvider, Settings, get_settings
from app.schemas.llm import LLMResult, parse_llm_estimation_payload
from app.services.prompts import build_system_prompt

# Deterministic CAG-style answers: stay close to few-shot examples, less invention.
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

    def generate(self, transcription: str) -> LLMResult:
        """Generate an estimation for the given transcription via LiteLLM.

        :arg transcription: Meeting transcription text (already validated by API).
        :return: Provider-normalized estimation result including confidence.
        :raises ValueError: If ``LLM_PROVIDER`` is unsupported or JSON is invalid.
        :raises Exception: Propagates provider/network errors from LiteLLM.
        """
        provider = self._resolve_provider()
        model = self.settings.resolved_model
        system_prompt = build_system_prompt()
        response = completion(
            model=self.settings.litellm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcription},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            response_format={"type": "json_object"},
            api_key=self._api_key_for_provider(provider),
        )
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return self._to_result(
            content,
            model=model,
            provider=provider,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=(
                getattr(usage, "completion_tokens", None) if usage else None
            ),
        )

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

    def _to_result(
        self,
        raw_content: str,
        *,
        model: str,
        provider: LLMProvider,
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> LLMResult:
        """Map raw provider text into a normalized ``LLMResult``.

        :arg raw_content: Raw model completion text.
        :arg model: Model id (without LiteLLM provider prefix).
        :arg provider: Active LLM provider.
        :arg prompt_tokens: Optional prompt token count.
        :arg completion_tokens: Optional completion token count.
        :return: Normalized result with parsed confidence.
        :raises ValueError: If the payload cannot be parsed.
        """
        payload = parse_llm_estimation_payload(raw_content)
        return LLMResult(
            estimation=payload.estimation,
            model=model,
            provider=provider.value,
            confidence=payload.confidence,
            confidence_rationale=payload.confidence_rationale,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def generate_estimation(transcription: str) -> LLMResult:
    """Convenience wrapper around ``LLMService.generate``.

    :arg transcription: Meeting transcription text.
    :return: Provider-normalized estimation result including confidence.
    :raises ValueError: If ``LLM_PROVIDER`` is unsupported or JSON is invalid.
    :raises Exception: Propagates provider/network errors from LiteLLM.
    """
    return LLMService().generate(transcription)
