"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Ensure Settings can load before importing the app.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.estimation import MIN_TRANSCRIPTION_LENGTH  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Avoid cross-test pollution from cached Settings.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    """ASGI test client for the FastAPI app.

    :return: Configured ``TestClient``.
    :raises: Does not raise under normal operation.
    """
    return TestClient(app)


@pytest.fixture
def valid_transcription() -> str:
    """Return a transcription that meets the minimum length.

    :return: Sample transcription string.
    :raises: Does not raise under normal operation.
    """
    base = (
        "Client needs a landing page with contact form, HubSpot CRM integration, "
        "and a blog with WYSIWYG. Timeline: 4 weeks. Design is ready in Figma."
    )
    if len(base) < MIN_TRANSCRIPTION_LENGTH:
        base = base + (" extra detail." * 10)
    return base[: max(MIN_TRANSCRIPTION_LENGTH, len(base))]
