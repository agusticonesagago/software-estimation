"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Ensure Settings can load before importing the app.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.estimation import MIN_DESCRIPTION_LENGTH  # noqa: E402
from app.services.sessions import session_store  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Avoid cross-test pollution from cached Settings.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_session_store() -> None:
    """Reset in-memory sessions between tests.

    :return: None.
    :raises: Does not raise under normal operation.
    """
    session_store.clear()
    yield
    session_store.clear()


@pytest.fixture
def client() -> TestClient:
    """ASGI test client for the FastAPI app.

    :return: Configured ``TestClient``.
    :raises: Does not raise under normal operation.
    """
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """Async HTTPX client bound to the FastAPI ASGI app.

    :return: Async iterator yielding a configured ``httpx.AsyncClient``.
    :raises: Does not raise under normal operation.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def valid_description() -> str:
    """Return a project description that meets the minimum length.

    :return: Sample description string.
    :raises: Does not raise under normal operation.
    """
    base = (
        "Build a B2B SaaS dashboard for inventory alerts with role-based access, "
        "Slack notifications, and CSV export."
    )
    if len(base) < MIN_DESCRIPTION_LENGTH:
        base = base + (" more detail" * 5)
    return base


@pytest.fixture
def valid_estimate_payload(valid_description: str) -> dict[str, str]:
    """Return a JSON-ready body for POST /api/v1/estimate.

    :arg valid_description: Description meeting min length.
    :return: Typed estimation request as a dict of strings.
    :raises: Does not raise under normal operation.
    """
    return {
        "description": valid_description,
        "project_type": "web_saas",
        "detail_level": "medium",
        "output_format": "phases_table",
    }
