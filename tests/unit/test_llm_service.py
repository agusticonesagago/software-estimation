"""Unit tests for LLMService with mocked LiteLLM."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.config import LLMProvider, Settings
from app.services.llm_service import LLMService, generate_estimation, stream_estimation

_SYSTEM = "You are an estimation specialist."
_USER = "Estimate this project: inventory SaaS dashboard."


def _openai_settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider=LLMProvider.OPENAI,
        openai_api_key="sk-test",
        llm_model="gpt-4o-mini",
    )


def _anthropic_settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider=LLMProvider.ANTHROPIC,
        anthropic_api_key="sk-ant-test",
        llm_model="claude-haiku-4-5",
    )


def _fake_completion_response(
    payload: str, *, prompt_tokens: int, completion_tokens: int
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def test_generate_openai_returns_free_text_with_separate_roles() -> None:
    """Call LiteLLM for OpenAI with distinct system and user messages.

    :return: None.
    :raises AssertionError: If messages or result fields are wrong.
    """
    fake = _fake_completion_response(
        "## Estimation: Demo\n\n| Phase | Hours |\n",
        prompt_tokens=11,
        completion_tokens=22,
    )

    with patch("app.services.llm_service.completion", return_value=fake) as mock_comp:
        result = LLMService(_openai_settings()).generate(_SYSTEM, _USER)

    mock_comp.assert_called_once()
    kwargs = mock_comp.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-4o-mini"
    assert kwargs["api_key"] == "sk-test"
    assert "response_format" not in kwargs
    assert kwargs["messages"] == [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _USER},
    ]
    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.estimation.startswith("## Estimation:")
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 22


def test_generate_anthropic_returns_free_text() -> None:
    """Call LiteLLM for Anthropic and return free-text content.

    :return: None.
    :raises AssertionError: If result fields are wrong.
    """
    fake = _fake_completion_response(
        "## Estimation: Anth\n\nNarrative body.",
        prompt_tokens=5,
        completion_tokens=7,
    )

    with patch("app.services.llm_service.completion", return_value=fake) as mock_comp:
        result = LLMService(_anthropic_settings()).generate(_SYSTEM, _USER)

    kwargs = mock_comp.call_args.kwargs
    assert kwargs["model"] == "anthropic/claude-haiku-4-5"
    assert kwargs["api_key"] == "sk-ant-test"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"
    assert result.provider == "anthropic"
    assert result.model == "claude-haiku-4-5"
    assert result.prompt_tokens == 5
    assert result.completion_tokens == 7


def test_generate_estimation_wrapper_uses_service() -> None:
    """Expose generate_estimation as a thin wrapper.

    :return: None.
    :raises AssertionError: If wrapper does not return the mocked result.
    """
    fake = MagicMock()
    with patch("app.services.llm_service.LLMService") as svc_cls:
        svc_cls.return_value.generate.return_value = fake
        assert generate_estimation(_SYSTEM, _USER) is fake


def test_generate_rejects_unsupported_provider() -> None:
    """Raise when provider is not openai/anthropic.

    :return: None.
    :raises AssertionError: If ValueError is not raised.
    """
    settings = MagicMock()
    settings.llm_provider = "azure"
    settings.resolved_model = "some-model"
    settings.litellm_model = "azure/some-model"
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        LLMService(settings).generate(_SYSTEM, _USER)


def test_generate_rejects_missing_api_key() -> None:
    """Raise when the active provider has no API key.

    :return: None.
    :raises AssertionError: If ValueError is not raised.
    """
    settings = MagicMock()
    settings.llm_provider = "openai"
    settings.resolved_model = "gpt-4o-mini"
    settings.litellm_model = "openai/gpt-4o-mini"
    settings.openai_api_key = None
    settings.anthropic_api_key = None
    with pytest.raises(ValueError, match="Missing API key"):
        LLMService(settings).generate(_SYSTEM, _USER)


def test_generate_stream_yields_token_deltas() -> None:
    """Stream LiteLLM chunks as text deltas with stream=True.

    :return: None.
    :raises AssertionError: If deltas or call kwargs are wrong.
    """
    chunks = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="He"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="llo"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
        {"choices": [{"delta": {"content": "!"}}]},
        {"choices": []},
    ]

    with patch("app.services.llm_service.completion", return_value=chunks) as mock_comp:
        pieces = list(LLMService(_openai_settings()).generate_stream(_SYSTEM, _USER))

    assert pieces == ["He", "llo", "!"]
    assert mock_comp.call_args.kwargs["stream"] is True
    assert mock_comp.call_args.kwargs["stream_options"] == {"include_usage": True}
    assert mock_comp.call_args.kwargs["messages"][0]["role"] == "system"


def test_generate_stream_captures_usage_from_final_chunk() -> None:
    """Store token usage reported on the final stream chunk.

    :return: None.
    :raises AssertionError: If usage is not captured on the service.
    """
    chunks = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="x"))],
            usage=None,
        ),
        SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4),
        ),
    ]
    service = LLMService(_openai_settings())
    with patch("app.services.llm_service.completion", return_value=chunks):
        assert list(service.generate_stream(_SYSTEM, _USER)) == ["x"]
    assert service.last_prompt_tokens == 10
    assert service.last_completion_tokens == 4


def test_stream_estimation_wrapper_uses_service() -> None:
    """Expose stream_estimation as a thin wrapper.

    :return: None.
    :raises AssertionError: If wrapper does not iterate the mocked stream.
    """
    with patch("app.services.llm_service.LLMService") as svc_cls:
        svc_cls.return_value.generate_stream.return_value = iter(["a", "b"])
        assert list(stream_estimation(_SYSTEM, _USER)) == ["a", "b"]
