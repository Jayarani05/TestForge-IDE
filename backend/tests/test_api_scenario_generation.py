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


API_CONTEXT = """File: app/api/v1/orders.py
Lines: 10-19
@router.post(
    "/orders",
    response_model=OrderResponse,
)
async def create_order(request: OrderRequest):
    return await order_service.create(request)
"""


def _api_scenarios(count: int, *, include_functional: bool = False) -> str:
    test_cases = [
        {
            "id": f"TC-API-{index:03d}",
            "title": f"POST /orders API contract {index}",
            "description": (
                "Verify POST /orders accepts an order request and returns "
                "the order response."
            ),
            "test_type": "api",
            "priority": "high",
            "preconditions": ["The order API is available."],
            "steps": [
                "Submit a valid order request to POST /orders.",
                "Validate the returned order response.",
            ],
            "expected_result": (
                "The endpoint returns an OrderResponse for the submitted order."
            ),
            "target_file": "app/api/v1/orders.py",
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
def api_generation_client(monkeypatch, tmp_path):
    repository = tmp_path / "api-repository"
    repository.mkdir()
    captured: dict[str, object] = {}
    route_chunk = ContextChunk(
        repository_path=str(repository),
        file_path=str(repository / "app" / "api" / "v1" / "orders.py"),
        relative_path="app/api/v1/orders.py",
        content=API_CONTEXT.split("Lines: 10-19\n", 1)[1],
        source_type=ContextSourceType.SOURCE_CODE,
        language="Python",
        start_line=10,
        end_line=19,
        chunk_type="file_segment",
    )

    class StubRetriever:
        async def retrieve(self, *, session, query):
            captured["query"] = query
            results = (
                []
                if captured.get("no_api_evidence")
                else [ContextResult(chunk=route_chunk, score=0.9)]
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


def test_api_only_generation_uses_route_context_and_structured_response(
    api_generation_client,
    monkeypatch,
):
    client, repository, captured = api_generation_client

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
                model="api-test",
                content=_api_scenarios(4, include_functional=True),
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
            "prompt": "Validate the order API contract.",
            "test_types": ["api"],
            "count": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["repository_path"] == str(repository)
    assert result["total_tests"] == 2
    assert len(result["test_cases"]) == 2
    assert all(
        scenario["test_type"] == "api"
        and scenario["steps"]
        and scenario["expected_result"]
        for scenario in result["test_cases"]
    )
    assert all(
        "POST /orders" in scenario["description"]
        for scenario in result["test_cases"]
    )

    query = captured["query"]
    assert query.query == "Validate the order API contract."
    assert query.repository_path == str(repository)
    assert query.top_k == 10

    llm_request = captured["llm_request"]
    assert "Requested test categories:\napi" in llm_request.prompt
    assert "API scenario instructions" in llm_request.prompt
    assert "HTTP methods" in llm_request.prompt
    assert "post" in llm_request.prompt.lower()
    assert "/orders" in llm_request.prompt
    assert "OrderResponse" in llm_request.prompt
    assert captured["provider_name"] == "auto"


def test_api_only_generation_returns_empty_when_context_has_no_api_evidence(
    api_generation_client,
    monkeypatch,
):
    client, repository, captured = api_generation_client
    captured["no_api_evidence"] = True

    class UnexpectedOrchestrator:
        async def generate(self, **kwargs):
            raise AssertionError(
                "generation must not run without API evidence"
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
            "prompt": "Generate API scenarios.",
            "test_types": ["api"],
            "count": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "repository_path": str(repository),
        "test_cases": [],
        "total_tests": 0,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {
            "repository_path": "repository",
            "prompt": "Generate API scenarios.",
            "test_types": ["unknown"],
            "count": 2,
        },
        {
            "repository_path": "repository",
            "prompt": "Generate API scenarios.",
            "test_types": ["api"],
            "count": 51,
        },
        {
            "repository_path": "repository",
            "test_types": ["api"],
            "count": 2,
        },
    ],
)
def test_api_scenario_generation_rejects_invalid_requests(
    api_generation_client,
    payload,
):
    client, _, _ = api_generation_client

    response = client.post(
        "/tests/generate",
        json=payload,
    )

    assert response.status_code == 422


def test_functional_only_generation_does_not_add_api_instructions(
    api_generation_client,
    monkeypatch,
):
    client, repository, captured = api_generation_client

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
                content=json.dumps({"test_cases": []}),
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
            "prompt": "Verify the order flow.",
            "test_types": ["functional"],
            "count": 2,
        },
    )

    assert response.status_code == 200
    assert (
        "Identify endpoints and HTTP methods"
        not in captured["llm_request"].prompt
    )


def test_openapi_context_is_recognized_as_api_evidence(
    monkeypatch,
    tmp_path,
):
    from app.agents.test_generator import TestGenerationAgent
    from app.agents.test_generation import TestGenerationRequest

    generator = TestGenerationAgent()
    request = TestGenerationRequest(
        repository_path=str(tmp_path),
        prompt="Test the orders API.",
        test_types=["api"],
        count=1,
    )
    received: dict[str, object] = {}

    class StubOrchestrator:
        async def generate(
            self,
            *,
            request,
            provider_name,
            fallback_providers,
        ):
            received["prompt"] = request.prompt
            return LLMResponse(
                provider="mock",
                model="openapi-test",
                content=_api_scenarios(1),
            )

    response = __import__("asyncio").run(
        generator.generate(
            request=request,
            context=(
                "openapi: 3.0.0\n"
                "paths:\n"
                "  /orders:\n"
                "    post:\n"
                "      responses:\n"
                "        '201':"
            ),
            orchestrator=StubOrchestrator(),
        )
    )

    assert response.total_tests == 1
    assert "openapi: 3.0.0" in received["prompt"]
