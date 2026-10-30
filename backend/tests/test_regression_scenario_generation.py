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


def _regression_scenarios(count: int, *, include_functional: bool = False) -> str:
    test_cases = [
        {
            "id": f"TC-REG-{index:03d}",
            "title": f"Preserve order persistence behavior {index}",
            "description": (
                "Protect the existing behavior evidenced by "
                "tests/test_orders.py: create_order persists and returns "
                "the submitted order."
            ),
            "test_type": "regression",
            "priority": "high",
            "preconditions": ["The order repository is configured."],
            "steps": [
                "Submit an order to create_order.",
                "Verify the repository receives the submitted order.",
                "Verify create_order returns the persisted order.",
            ],
            "expected_result": (
                "The submitted order is persisted and the persisted order "
                "is returned."
            ),
            "target_file": "src/orders.py",
            "target_function": "create_order",
        }
        for index in range(1, count + 1)
    ]

    if include_functional:
        test_cases.append(
            {
                **test_cases[0],
                "id": "TC-FUNC-001",
                "title": "Unrequested functional scenario",
                "test_type": "functional",
            }
        )

    return json.dumps({"test_cases": test_cases})


@pytest.fixture
def regression_generation_client(monkeypatch, tmp_path):
    repository = tmp_path / "regression-repository"
    repository.mkdir()
    captured: dict[str, object] = {}
    chunks = [
        ContextChunk(
            repository_path=str(repository),
            file_path=str(repository / "src" / "orders.py"),
            relative_path="src/orders.py",
            content=(
                "def create_order(repository, order):\n"
                "    return repository.save(order)"
            ),
            source_type=ContextSourceType.SOURCE_CODE,
            language="Python",
            start_line=1,
            end_line=2,
            chunk_type="file_segment",
        ),
        ContextChunk(
            repository_path=str(repository),
            file_path=str(repository / "tests" / "test_orders.py"),
            relative_path="tests/test_orders.py",
            content=(
                "def test_create_order_persists_and_returns_order():\n"
                "    order = {\"sku\": \"item-1\"}\n"
                "    assert create_order(repository, order) == order"
            ),
            source_type=ContextSourceType.SOURCE_CODE,
            language="Python",
            start_line=1,
            end_line=3,
            chunk_type="file_segment",
        ),
    ]

    class StubRetriever:
        async def retrieve(self, *, session, query):
            captured["query"] = query
            results = (
                []
                if captured.get("no_repository_evidence")
                else [
                    ContextResult(chunk=chunk, score=0.9)
                    for chunk in chunks
                ]
            )
            return ContextResponse(
                query=query.query,
                repository_path=str(repository),
                results=results,
                total_results=len(results),
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


def test_regression_only_generation_uses_repository_context_and_requested_count(
    regression_generation_client,
    monkeypatch,
):
    client, repository, captured = regression_generation_client

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
                model="regression-test",
                content=_regression_scenarios(4, include_functional=True),
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
            "prompt": "Protect existing order creation behavior.",
            "test_types": ["regression"],
            "count": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["repository_path"] == str(repository)
    assert result["total_tests"] == len(result["test_cases"]) == 2
    assert all(
        scenario["test_type"] == "regression"
        and scenario["steps"]
        and scenario["expected_result"]
        and scenario["target_file"] == "src/orders.py"
        and scenario["target_function"] == "create_order"
        for scenario in result["test_cases"]
    )

    query = captured["query"]
    assert query.query == "Protect existing order creation behavior."
    assert query.repository_path == str(repository)
    assert query.top_k == 10

    llm_request = captured["llm_request"]
    assert "Requested test categories:\nregression" in llm_request.prompt
    assert "Regression scenario instructions" in llm_request.prompt
    assert "existing behavior" in llm_request.prompt
    assert "tests/test_orders.py" in llm_request.prompt
    assert "create_order(repository, order)" in llm_request.prompt
    assert "Git history" in llm_request.prompt
    assert "do not claim a" in llm_request.prompt
    assert captured["provider_name"] == "auto"


def test_regression_only_generation_returns_empty_without_repository_evidence(
    regression_generation_client,
    monkeypatch,
):
    client, repository, captured = regression_generation_client
    captured["no_repository_evidence"] = True

    class UnexpectedOrchestrator:
        async def generate(self, **kwargs):
            raise AssertionError(
                "generation must not run without repository evidence"
            )

    monkeypatch.setattr(
        test_generation_api,
        "orchestrator",
        UnexpectedOrchestrator(),
    )

    response = client.post(
        "/tests/generate",
        json={
            "repository_path": str(repository),
            "prompt": "Generate regression scenarios.",
            "test_types": ["regression"],
            "count": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "repository_path": str(repository),
        "test_cases": [],
        "total_tests": 0,
    }


def test_functional_only_generation_does_not_add_regression_guidance(
    regression_generation_client,
    monkeypatch,
):
    client, repository, captured = regression_generation_client

    class StubOrchestrator:
        async def generate(
            self,
            *,
            request,
            provider_name,
            fallback_providers,
        ):
            captured["llm_request"] = request
            return LLMResponse(
                provider="mock",
                model="functional-test",
                content='{"test_cases": []}',
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
            "prompt": "Verify the existing order flow.",
            "test_types": ["functional"],
            "count": 2,
        },
    )

    assert response.status_code == 200
    assert (
        "Identify existing behavior from the"
        not in captured["llm_request"].prompt
    )
