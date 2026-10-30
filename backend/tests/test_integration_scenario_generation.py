from collections.abc import AsyncGenerator
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.providers.base import LLMResponse
from app.api.v1 import test_generation as test_generation_api
from app.context.models import (
    ContextChunk,
    ContextResponse,
    ContextResult,
    ContextSourceType,
)
from app.core.database import get_db
from app.main import app


def _integration_scenarios(count: int) -> str:
    return json.dumps(
        {
            "test_cases": [
                {
                    "id": f"TC-{index:03d}",
                    "title": f"Service integration scenario {index}",
                    "description": (
                        "Verify data is passed from the order service "
                        "to the repository and the stored result is returned."
                    ),
                    "test_type": "integration",
                    "priority": "high",
                    "preconditions": [
                        "The repository-backed order service is configured."
                    ],
                    "steps": [
                        "Submit an order through the service.",
                        "Verify the service calls the repository with the order.",
                        "Read the created order through the service."
                    ],
                    "expected_result": (
                        "The repository stores the order and the service "
                        "returns the stored order."
                    ),
                    "target_file": "src/order_service.py",
                    "target_function": "create_order",
                }
                for index in range(1, count + 1)
            ]
        }
    )


@pytest.fixture
def context_generation_client(monkeypatch, tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    captured: dict[str, object] = {}

    chunk = ContextChunk(
        repository_path=str(repository),
        file_path=str(repository / "src" / "order_service.py"),
        relative_path="src/order_service.py",
        content=(
            "class OrderService:\n"
            "    def create_order(self, order):\n"
            "        return self.repository.save(order)"
        ),
        source_type=ContextSourceType.SOURCE_CODE,
        language="Python",
        start_line=1,
        end_line=3,
        chunk_type="file_segment",
    )

    class StubRetriever:
        async def retrieve(self, *, session, query):
            captured["query"] = query
            return ContextResponse(
                query=query.query,
                repository_path=str(repository),
                results=[ContextResult(chunk=chunk, score=0.9)],
                total_results=1,
            )

    monkeypatch.setattr(
        test_generation_api,
        "hybrid_retriever",
        StubRetriever(),
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, repository, captured

    app.dependency_overrides.pop(get_db, None)


def test_integration_generation_uses_repository_context_and_requested_count(
    context_generation_client,
    monkeypatch,
):
    client, repository, captured = context_generation_client

    class StubOrchestrator:
        async def generate(
            self,
            *,
            request,
            provider_name,
            fallback_providers,
        ):
            captured["llm_request"] = request
            captured["provider_name"] = provider_name
            return LLMResponse(
                provider="mock",
                model="integration-test",
                content=_integration_scenarios(4),
            )

    monkeypatch.setattr(
        test_generation_api,
        "orchestrator",
        StubOrchestrator(),
    )

    response = client.post(
        "/tests/generate",
        json={
            "repository_path": str(repository),
            "prompt": "Verify service and persistence interactions.",
            "test_types": ["integration"],
            "count": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["repository_path"] == str(repository)
    assert result["total_tests"] == 2
    assert len(result["test_cases"]) == 2
    assert all(
        item["test_type"] == "integration"
        for item in result["test_cases"]
    )
    assert all(
        item["expected_result"]
        and item["steps"]
        and item["target_file"] == "src/order_service.py"
        for item in result["test_cases"]
    )

    query = captured["query"]
    assert query.query == "Verify service and persistence interactions."
    assert query.repository_path == str(repository)
    assert query.top_k == 10

    llm_request = captured["llm_request"]
    assert "Requested test categories:\nintegration" in llm_request.prompt
    assert "integration scenario instructions" in llm_request.prompt.lower()
    assert "File: src/order_service.py\nLines: 1-3" in llm_request.prompt
    assert "self.repository.save(order)" in llm_request.prompt
    assert "interactions between" in llm_request.prompt.lower()
    assert captured["provider_name"] == "auto"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "repository_path": "repository",
            "prompt": "Generate integration scenarios.",
            "test_types": ["unknown"],
            "count": 2,
        },
        {
            "repository_path": "repository",
            "prompt": "Generate integration scenarios.",
            "test_types": ["integration"],
            "count": 51,
        },
        {
            "repository_path": "repository",
            "test_types": ["integration"],
            "count": 2,
        },
    ],
)
def test_integration_generation_rejects_invalid_requests(
    context_generation_client,
    payload,
):
    client, _, _ = context_generation_client

    response = client.post(
        "/tests/generate",
        json=payload,
    )

    assert response.status_code == 422


def test_integration_generation_returns_empty_result_without_failure(
    context_generation_client,
    monkeypatch,
):
    client, repository, _ = context_generation_client

    class EmptyResultOrchestrator:
        async def generate(
            self,
            *,
            request,
            provider_name,
            fallback_providers,
        ):
            return LLMResponse(
                provider="mock",
                model="integration-test",
                content='{"test_cases": []}',
            )

    monkeypatch.setattr(
        test_generation_api,
        "orchestrator",
        EmptyResultOrchestrator(),
    )

    response = client.post(
        "/tests/generate",
        json={
            "repository_path": str(repository),
            "prompt": "Generate integration scenarios.",
            "test_types": ["integration"],
            "count": 2,
        },
    )

    assert response.status_code == 200
    assert response.json()["test_cases"] == []
    assert response.json()["total_tests"] == 0


def test_integration_generation_failure_is_not_returned_as_success(
    context_generation_client,
    monkeypatch,
):
    client, repository, _ = context_generation_client

    class FailedOrchestrator:
        async def generate(
            self,
            *,
            request,
            provider_name,
            fallback_providers,
        ):
            raise RuntimeError("mock provider failed")

    monkeypatch.setattr(
        test_generation_api,
        "orchestrator",
        FailedOrchestrator(),
    )

    response = client.post(
        "/tests/generate",
        json={
            "repository_path": str(repository),
            "prompt": "Generate integration scenarios.",
            "test_types": ["integration"],
            "count": 2,
        },
    )

    assert response.status_code == 500
    assert "test_cases" not in response.json()
