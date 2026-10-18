"""Application configuration loaded from environment variables."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    """Supported LLM providers routed through LiteLLM."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    """Runtime settings for LLM provider selection and app environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_model: str | None = None
    app_env: str = "development"
    log_level: str = "DEBUG"

    default_openai_model: str = Field(default="gpt-4o-mini", exclude=True)
    default_anthropic_model: str = Field(default="claude-haiku-4-5", exclude=True)

    @model_validator(mode="after")
    def validate_provider_and_model(self) -> "Settings":
        """Ensure the active provider has a key and a resolved model id.

        :return: Validated settings instance with a concrete ``llm_model``.
        :raises ValueError: If the active provider API key is missing.
        """
        if self.llm_provider is LLMProvider.OPENAI:
            if not self.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
                )
            if not self.llm_model:
                self.llm_model = self.default_openai_model
        elif self.llm_provider is LLMProvider.ANTHROPIC:
            if not self.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
                )
            if not self.llm_model:
                self.llm_model = self.default_anthropic_model
        return self

    @property
    def resolved_model(self) -> str:
        """Return the concrete model id after validation.

        :return: Non-null LLM model identifier (without LiteLLM prefix).
        :raises AssertionError: If ``llm_model`` was not set by validation.
        """
        assert self.llm_model is not None
        return self.llm_model

    @property
    def litellm_model(self) -> str:
        """Return the LiteLLM model string ``provider/model``.

        If ``LLM_MODEL`` already includes a provider prefix (contains ``/``),
        it is returned unchanged so advanced users can pass routes like
        ``openai/gpt-4o-mini`` directly.

        :return: Model id accepted by ``litellm.completion``.
        :raises AssertionError: If ``llm_model`` was not set by validation.
        """
        model = self.resolved_model
        if "/" in model:
            return model
        return f"{self.llm_provider.value}/{model}"


@lru_cache
def get_settings() -> Settings:
    """Load and cache application settings from the environment.

    :return: Cached ``Settings`` instance.
    :raises ValidationError: If environment values fail Settings validation.
    """
    return Settings()


__all__ = ["LLMProvider", "Settings", "ValidationError", "get_settings"]
