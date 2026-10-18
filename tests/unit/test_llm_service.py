"""Unit tests for LLMService with mocked LiteLLM."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.config import LLMProvider, Settings
from app.services.llm_service import LLMService, generate_estimation


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


def test_generate_openai_parses_json_payload() -> None:
    """Call LiteLLM for OpenAI and map JSON into LLMResult.

    :return: None.
    :raises AssertionError: If result fields are wrong.
    """
    payload = (
        '{"estimation":"## Estimation: Demo","confidence":0.9,'
        '"confidence_rationale":"Clear scope"}'
    )
    fake = _fake_completion_response(payload, prompt_tokens=11, completion_tokens=22)

    with patch("app.services.llm_service.completion", return_value=fake) as mock_comp:
        result = LLMService(_openai_settings()).generate("x" * 120)

    mock_comp.assert_called_once()
    kwargs = mock_comp.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-4o-mini"
    assert kwargs["api_key"] == "sk-test"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.estimation.startswith("## Estimation:")
    assert result.confidence == 0.9
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 22


def test_generate_anthropic_parses_json_payload() -> None:
    """Call LiteLLM for Anthropic and map JSON into LLMResult.

    :return: None.
    :raises AssertionError: If result fields are wrong.
    """
    payload = (
        '{"estimation":"## Estimation: Anth","confidence":0.55,'
        '"confidence_rationale":"Some unknowns"}'
    )
    fake = _fake_completion_response(payload, prompt_tokens=5, completion_tokens=7)

    with patch("app.services.llm_service.completion", return_value=fake) as mock_comp:
        result = LLMService(_anthropic_settings()).generate("y" * 120)

    kwargs = mock_comp.call_args.kwargs
    assert kwargs["model"] == "anthropic/claude-haiku-4-5"
    assert kwargs["api_key"] == "sk-ant-test"
    assert result.provider == "anthropic"
    assert result.model == "claude-haiku-4-5"
    assert result.confidence == 0.55
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
        assert generate_estimation("z" * 120) is fake


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
        LLMService(settings).generate("a" * 120)


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
        LLMService(settings).generate("b" * 120)
