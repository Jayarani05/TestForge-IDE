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


def _boundary_scenarios() -> str:
    return json.dumps(
        {
            "test_cases": [
                {
                    "id": "TC-BND-001",
                    "title": "Reject count below minimum",
                    "description": (
                        "Verify the documented lower bound ge=1 rejects "
                        "a count of 0."
                    ),
                    "test_type": "boundary",
                    "priority": "high",
                    "preconditions": ["The test generation API is available."],
                    "steps": [
                        "Submit a generation request with count=0.",
                        "Inspect the HTTP response.",
                    ],
                    "expected_result": (
                        "The request is rejected by count validation."
                    ),
                    "target_file": "app/agents/test_generation.py",
                    "target_function": "TestGenerationRequest",
                },
                {
                    "id": "TC-BND-002",
                    "title": "Accept count at minimum",
                    "description": (
                        "Verify the documented lower bound ge=1 accepts "
                        "a count of 1."
                    ),
                    "test_type": "boundary",
                    "priority": "high",
                    "preconditions": ["The test generation API is available."],
                    "steps": [
                        "Submit a valid generation request with count=1.",
                        "Inspect the HTTP response.",
                    ],
                    "expected_result": (
                        "The request passes count validation."
                    ),
                    "target_file": "app/agents/test_generation.py",
                    "target_function": "TestGenerationRequest",
                },
                {
                    "id": "TC-BND-003",
                    "title": "Accept count at maximum",
                    "description": (
                        "Verify the documented upper bound le=50 accepts "
                        "a count of 50."
                    ),
                    "test_type": "boundary",
                    "priority": "high",
                    "preconditions": ["The test generation API is available."],
                    "steps": [
                        "Submit a valid generation request with count=50.",
                        "Inspect the HTTP response.",
                    ],
                    "expected_result": (
                        "The request passes count validation."
                    ),
                    "target_file": "app/agents/test_generation.py",
                    "target_function": "TestGenerationRequest",
                },
                {
                    "id": "TC-BND-004",
                    "title": "Reject count above maximum",
                    "description": (
                        "Verify the documented upper bound le=50 rejects "
                        "a count of 51."
                    ),
                    "test_type": "boundary",
                    "priority": "high",
                    "preconditions": ["The test generation API is available."],
                    "steps": [
                        "Submit a generation request with count=51.",
                        "Inspect the HTTP response.",
                    ],
                    "expected_result": (
                        "The request is rejected by count validation."
                    ),
                    "target_file": "app/agents/test_generation.py",
                    "target_function": "TestGenerationRequest",
                },
                {
                    "id": "TC-FUNC-001",
                    "title": "Unrequested functional scenario",
                    "description": "Unrequested category.",
                    "test_type": "functional",
                    "priority": "medium",
                    "preconditions": [],
                    "steps": ["Run the functional behavior."],
                    "expected_result": "The behavior works.",
                    "target_file": None,
                    "target_function": None,
                },
            ]
        }
    )


@pytest.fixture
def boundary_generation_client(monkeypatch, tmp_path):
    repository = tmp_path / "boundary-repository"
    repository.mkdir()
    captured: dict[str, object] = {}
    chunks = [
        ContextChunk(
            repository_path=str(repository),
            file_path=str(repository / "app" / "agents" / "test_generation.py"),
            relative_path="app/agents/test_generation.py",
            content=(
                "class TestGenerationRequest(BaseModel):\n"
                "    count: int = Field(default=10, ge=1, le=50)"
            ),
            source_type=ContextSourceType.SOURCE_CODE,
            language="Python",
            start_line=30,
            end_line=31,
            chunk_type="file_segment",
        ),
        ContextChunk(
            repository_path=str(repository),
            file_path=str(repository / "backend_tests" / "test_count.py"),
            relative_path="backend_tests/test_count.py",
            content=(
                "@pytest.mark.parametrize(\"count\", [0, 1, 50, 51])\n"
                "def test_count_validation_boundaries(count):\n"
                "    ..."
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
                if captured.get("no_boundary_evidence")
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


def test_boundary_only_generation_uses_evidence_and_respects_count(
    boundary_generation_client,
    monkeypatch,
):
    client, repository, captured = boundary_generation_client

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
                model="boundary-test",
                content=_boundary_scenarios(),
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
            "prompt": "Check the accepted count limits.",
            "test_types": ["boundary"],
            "count": 4,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["repository_path"] == str(repository)
    assert result["total_tests"] == len(result["test_cases"]) == 4
    assert all(
        scenario["test_type"] == "boundary"
        and scenario["steps"]
        and scenario["expected_result"]
        and scenario["target_file"] == "app/agents/test_generation.py"
        for scenario in result["test_cases"]
    )
    descriptions = " ".join(
        scenario["description"]
        for scenario in result["test_cases"]
    )
    steps = " ".join(
        step
        for scenario in result["test_cases"]
        for step in scenario["steps"]
    )
    assert "ge=1" in descriptions
    assert "le=50" in descriptions
    assert all(value in descriptions + steps for value in ("0", "1", "50", "51"))

    query = captured["query"]
    assert query.query == "Check the accepted count limits."
    assert query.repository_path == str(repository)
    assert query.top_k == 10

    llm_request = captured["llm_request"]
    assert "Requested test categories:\nboundary" in llm_request.prompt
    assert "Boundary scenario instructions" in llm_request.prompt
    assert "ge=1, le=50" in llm_request.prompt
    assert "below, at, and above" in llm_request.prompt
    assert captured["provider_name"] == "auto"


def test_boundary_only_generation_returns_empty_without_constraints(
    boundary_generation_client,
    monkeypatch,
):
    client, repository, captured = boundary_generation_client
    captured["no_boundary_evidence"] = True

    class UnexpectedOrchestrator:
        async def generate(self, **kwargs):
            raise AssertionError(
                "generation must not run without boundary evidence"
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
            "prompt": "Generate boundary scenarios.",
            "test_types": ["boundary"],
            "count": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "repository_path": str(repository),
        "test_cases": [],
        "total_tests": 0,
    }


def test_functional_only_generation_does_not_add_boundary_guidance(
    boundary_generation_client,
    monkeypatch,
):
    client, repository, captured = boundary_generation_client

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
            "prompt": "Verify the functional workflow.",
            "test_types": ["functional"],
            "count": 2,
        },
    )

    assert response.status_code == 200
    assert (
        "Identify explicit constraints in the"
        not in captured["llm_request"].prompt
    )
