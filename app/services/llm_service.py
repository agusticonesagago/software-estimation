"""LLM service: provider-agnostic calls via LiteLLM (and OpenAI Responses for files)."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from litellm import completion
from openai import OpenAI

from app.config import LLMProvider, Settings, get_settings
from app.schemas.llm import LLMResult
from app.services.attachments import UploadedAttachment

# Deterministic answers: stay close to prompt examples, less invention.
_LLM_TEMPERATURE = 0.0
_LLM_MAX_TOKENS = 4096


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
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def generate_with_attachments(
        self,
        system: str,
        user: str,
        attachments: Sequence[UploadedAttachment],
    ) -> LLMResult:
        """Generate an estimation with Path A multimodal file references.

        Convenience wrapper that builds a two-message chat and delegates to
        ``generate_from_messages``.

        :arg system: Rendered system prompt.
        :arg user: Rendered user prompt / transcript wrapper.
        :arg attachments: Provider-ready Path A uploads.
        :return: Provider-normalized free-text estimation result.
        :raises ValueError: If provider/key is invalid or an attachment is incomplete.
        :raises Exception: Propagates provider/network errors.
        """
        return self.generate_from_messages(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            attachments=attachments,
        )

    def generate_from_messages(
        self,
        messages: Sequence[dict[str, Any]],
        attachments: Sequence[UploadedAttachment] = (),
    ) -> LLMResult:
        """Generate from a full chat ``messages`` array (sliding-window ready).

        Without attachments, calls LiteLLM ``completion`` with ``messages``.
        With attachments (Path A), keeps prior turns and attaches files to the
        latest user turn (OpenAI Responses or Anthropic multimodal blocks).

        :arg messages: OpenAI-style chat messages; first may be ``system``.
        :arg attachments: Optional Path A uploads for the current user turn.
        :return: Provider-normalized free-text estimation result.
        :raises ValueError: If ``messages`` is empty or attachments are incomplete.
        :raises Exception: Propagates provider/network errors.
        """
        if not messages:
            raise ValueError("messages must be non-empty")
        if not attachments:
            return self._complete_messages(list(messages))

        provider = self._resolve_provider()
        system, prior, last_user = self._split_messages(messages)
        if provider is LLMProvider.OPENAI:
            return self._generate_openai_responses(
                system=system,
                prior=prior,
                user=last_user,
                attachments=attachments,
            )
        return self._generate_anthropic_files(
            system=system,
            prior=prior,
            user=last_user,
            attachments=attachments,
        )

    def _complete_messages(self, messages: list[dict[str, Any]]) -> LLMResult:
        """Run LiteLLM chat completions on a prepared messages list.

        :arg messages: Full chat payload including system when present.
        :return: Normalized LLM result.
        :raises ValueError: If the provider or API key is invalid.
        :raises Exception: Propagates LiteLLM/provider errors.
        """
        provider = self._resolve_provider()
        response = completion(
            model=self.settings.litellm_model,
            messages=messages,
            temperature=_LLM_TEMPERATURE,
            max_tokens=_LLM_MAX_TOKENS,
            api_key=self._api_key_for_provider(provider),
            stream=False,
        )
        content = (response.choices[0].message.content or "").strip()
        usage = getattr(response, "usage", None)
        prompt_tokens, completion_tokens = self._usage_tokens(usage)
        self.last_prompt_tokens = prompt_tokens
        self.last_completion_tokens = completion_tokens
        return LLMResult(
            estimation=content,
            model=self.settings.resolved_model,
            provider=provider.value,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    @staticmethod
    def _split_messages(
        messages: Sequence[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]], str]:
        """Split chat messages into system, prior turns, and latest user text.

        :arg messages: Chat messages for the current call.
        :return: ``(system_text, prior_messages, last_user_text)``.
        :raises ValueError: If there is no trailing user message with text.
        """
        items = list(messages)
        system = ""
        body = items
        if items and items[0].get("role") == "system":
            system = str(items[0].get("content") or "")
            body = items[1:]
        if not body or body[-1].get("role") != "user":
            raise ValueError("messages must end with a user turn")
        last = body[-1].get("content")
        if not isinstance(last, str) or not last.strip():
            raise ValueError("last user message must be non-empty text")
        return system, body[:-1], last.strip()

    def _generate_openai_responses(
        self,
        *,
        system: str,
        prior: Sequence[dict[str, Any]],
        user: str,
        attachments: Sequence[UploadedAttachment],
    ) -> LLMResult:
        """Call OpenAI Responses with history plus Files API ids.

        :arg system: System instructions.
        :arg prior: Earlier user/assistant turns (no system).
        :arg user: Latest user text content.
        :arg attachments: Uploads that must include ``file_id``.
        :return: Normalized LLM result.
        :raises ValueError: If the API key or a ``file_id`` is missing.
        :raises Exception: Propagates OpenAI SDK errors.
        """
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for attachment estimates")
        content: list[dict[str, Any]] = [{"type": "input_text", "text": user}]
        for item in attachments:
            if not item.file_id:
                raise ValueError(f"OpenAI attachment missing file_id: {item.filename}")
            content.append({"type": "input_file", "file_id": item.file_id})

        input_items: list[dict[str, Any]] = [
            {"role": msg["role"], "content": msg["content"]} for msg in prior
        ]
        input_items.append({"role": "user", "content": content})

        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.responses.create(
            model=self.settings.resolved_model,
            instructions=system or None,
            input=input_items,
            temperature=_LLM_TEMPERATURE,
            max_output_tokens=_LLM_MAX_TOKENS,
        )
        text = (getattr(response, "output_text", None) or "").strip()
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", None) if usage else None
        completion_tokens = getattr(usage, "output_tokens", None) if usage else None
        self.last_prompt_tokens = prompt_tokens
        self.last_completion_tokens = completion_tokens
        return LLMResult(
            estimation=text,
            model=self.settings.resolved_model,
            provider=LLMProvider.OPENAI.value,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _generate_anthropic_files(
        self,
        *,
        system: str,
        prior: Sequence[dict[str, Any]],
        user: str,
        attachments: Sequence[UploadedAttachment],
    ) -> LLMResult:
        """Call LiteLLM with history plus Anthropic multimodal ``file_data`` blocks.

        :arg system: System prompt.
        :arg prior: Earlier user/assistant turns (no system).
        :arg user: Latest user text content.
        :arg attachments: Uploads that must include ``file_data_url``.
        :return: Normalized LLM result.
        :raises ValueError: If a data-URL is missing.
        :raises Exception: Propagates LiteLLM/provider errors.
        """
        user_content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for item in attachments:
            if not item.file_data_url:
                raise ValueError(
                    f"Anthropic attachment missing file_data_url: {item.filename}"
                )
            user_content.append(
                {
                    "type": "file",
                    "file": {
                        "file_data": item.file_data_url,
                        "format": "application/pdf",
                    },
                }
            )
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(prior)
        messages.append({"role": "user", "content": user_content})
        return self._complete_messages(messages)

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
            "temperature": _LLM_TEMPERATURE,
            "max_tokens": _LLM_MAX_TOKENS,
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
