"""Integration tests for POST /embeddings/ingest (OpenAI mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.embedding_pipeline.schemas import EMBEDDING_DIMENSIONS


def _budget_payload() -> dict[str, object]:
    """Minimal ingest body with one component.

    :return: JSON-serialisable ingest payload.
    :raises: Does not raise under normal operation.
    """
    return {
        "budgets": [
            {
                "budget_id": "BUD-2024-014",
                "client_metadata": {
                    "name": "FintechCorp",
                    "sector": "finance",
                    "country": "ES",
                },
                "project_summary": "Mobile banking API with OAuth 2.0",
                "main_technology": "ruby_on_rails",
                "year": 2024,
                "total_estimated_hours": 120,
                "components": [
                    {
                        "component_id": "AUTH-001",
                        "name": "OAuth 2.0 authentication backend",
                        "description": "OAuth flows with JWT session management.",
                        "tech_stack": ["ruby_on_rails", "postgresql"],
                        "estimated_hours": 120,
                        "complexity": "high",
                        "dependencies": [],
                    }
                ],
            }
        ]
    }


def test_ingest_embeddings_happy_path(client: TestClient) -> None:
    """Ingest should chunk, call OpenAI once, and return vectors + stats.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If response shape or status is wrong.
    """
    fake_vector = [0.01] * EMBEDDING_DIMENSIONS
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(index=0, embedding=fake_vector)]
    )

    with patch(
        "app.embedding_pipeline.router.OpenAIEmbedder"
    ) as embedder_cls:
        # Use a real embedder wired to the fake OpenAI client.
        from app.embedding_pipeline.embedder import OpenAIEmbedder

        embedder_cls.side_effect = lambda **kwargs: OpenAIEmbedder(
            client=mock_client,
            batch_size=100,
        )
        response = client.post("/embeddings/ingest", json=_budget_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["stats"]["total_budgets"] == 1
    assert body["stats"]["total_chunks"] == 1
    assert body["stats"]["total_tokens"] > 0
    assert body["stats"]["estimated_cost_usd"] >= 0.0
    assert body["chunks"][0]["chunk_id"] == "BUD-2024-014::AUTH-001"
    assert len(body["chunks"][0]["embedding"]) == EMBEDDING_DIMENSIONS


def test_ingest_embeddings_provider_error_returns_500(client: TestClient) -> None:
    """Unexpected provider failures should become a generic 500.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If status / detail are wrong.
    """
    with patch(
        "app.embedding_pipeline.router.OpenAIEmbedder"
    ) as embedder_cls:
        instance = MagicMock()
        instance.embed_many.side_effect = RuntimeError("boom")
        embedder_cls.return_value = instance
        response = client.post("/embeddings/ingest", json=_budget_payload())

    assert response.status_code == 500
    assert response.json()["detail"] == "Embedding provider error"


def test_embeddings_route_listed_in_openapi(client: TestClient) -> None:
    """Swagger schema must advertise POST /embeddings/ingest.

    :arg client: FastAPI test client.
    :return: None.
    :raises AssertionError: If the path is missing from OpenAPI.
    """
    schema = client.get("/openapi.json").json()
    assert "/embeddings/ingest" in schema["paths"]
    assert "post" in schema["paths"]["/embeddings/ingest"]
