"""Unit tests for application Settings."""

import pytest
from pydantic import ValidationError

from app.config import LLMProvider, Settings, get_settings


def test_openai_requires_api_key() -> None:
    """Fail when OpenAI is selected without an API key.

    :return: None.
    :raises AssertionError: If missing key is accepted.
    """
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="openai", openai_api_key=None)


def test_anthropic_requires_api_key() -> None:
    """Fail when Anthropic is selected without an API key.

    :return: None.
    :raises AssertionError: If missing key is accepted.
    """
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key=None)


def test_openai_defaults_model() -> None:
    """Default to gpt-4o-mini when OpenAI model is omitted.

    :return: None.
    :raises AssertionError: If the default model is wrong.
    """
    settings = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_api_key="sk-test",
        llm_model=None,
    )
    assert settings.resolved_model == "gpt-4o-mini"
    assert settings.llm_provider is LLMProvider.OPENAI


def test_anthropic_defaults_model() -> None:
    """Default to claude-haiku-4-5 when Anthropic model is omitted.

    :return: None.
    :raises AssertionError: If the default model is wrong.
    """
    settings = Settings(
        _env_file=None,
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test",
        llm_model=None,
    )
    assert settings.resolved_model == "claude-haiku-4-5"
    assert settings.llm_provider is LLMProvider.ANTHROPIC


def test_rejects_unknown_llm_provider() -> None:
    """Reject providers outside ``LLMProvider``.

    :return: None.
    :raises AssertionError: If an unknown provider is accepted.
    """
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="azure", openai_api_key="sk-test")


def test_litellm_model_adds_provider_prefix() -> None:
    """Expose LiteLLM ``provider/model`` from settings.

    :return: None.
    :raises AssertionError: If the LiteLLM model string is wrong.
    """
    openai = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_api_key="sk-test",
        llm_model="gpt-4o-mini",
    )
    anthropic = Settings(
        _env_file=None,
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test",
        llm_model="claude-haiku-4-5",
    )
    prefixed = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_api_key="sk-test",
        llm_model="openai/gpt-4o-mini",
    )
    assert openai.litellm_model == "openai/gpt-4o-mini"
    assert anthropic.litellm_model == "anthropic/claude-haiku-4-5"
    assert prefixed.litellm_model == "openai/gpt-4o-mini"


def test_get_settings_returns_cached_instance() -> None:
    """Cache Settings via get_settings lru_cache.

    :return: None.
    :raises AssertionError: If cache does not return the same object.
    """
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()
