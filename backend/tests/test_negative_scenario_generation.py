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


def _negative_scenarios() -> str:
    return json.dumps(
        {
            "test_cases": [
                {
                    "id": "TC-NEG-001",
                    "title": "Reject request with missing prompt",
                    "description": (
                        "Verify the required prompt field is rejected when "
                        "omitted from a generation request."
                    ),
                    "test_type": "negative",
                    "priority": "high",
                    "preconditions": ["The test generation API is available."],
                    "steps": [
                        "Submit a generation request without the prompt field.",
                        "Inspect the HTTP response.",
                    ],
                    "expected_result": (
                        "The request fails validation with HTTP 422."
                    ),
                    "target_file": "app/agents/test_generation.py",
                    "target_function": "TestGenerationRequest",
                },
                {
                    "id": "TC-NEG-002",
                    "title": "Reject empty prompt",
                    "description": (
                        "Verify prompt minimum length rejects an empty string."
                    ),
                    "test_type": "negative",
                    "priority": "high",
                    "preconditions": ["The test generation API is available."],
                    "steps": [
                        "Submit a generation request with prompt=\"\".",
                        "Inspect the HTTP response.",
                    ],
                    "expected_result": (
                        "The request fails validation with HTTP 422."
                    ),
                    "target_file": "app/agents/test_generation.py",
                    "target_function": "TestGenerationRequest",
                },
                {
                    "id": "TC-NEG-003",
                    "title": "Reject count above supported maximum",
                    "description": (
                        "Verify the request count limit rejects a value above "
                        "le=50."
                    ),
                    "test_type": "negative",
                    "priority": "high",
                    "preconditions": ["The test generation API is available."],
                    "steps": [
                        "Submit a generation request with count=51.",
                        "Inspect the HTTP response.",
                    ],
                    "expected_result": (
                        "The request fails validation with HTTP 422."
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
def negative_generation_client(monkeypatch, tmp_path):
    repository = tmp_path / "negative-repository"
    repository.mkdir()
    captured: dict[str, object] = {}
    chunks = [
        ContextChunk(
            repository_path=str(repository),
            file_path=str(repository / "app" / "agents" / "test_generation.py"),
            relative_path="app/agents/test_generation.py",
            content=(
                "class TestGenerationRequest(BaseModel):\n"
                "    prompt: str = Field(..., min_length=1)\n"
                "    count: int = Field(default=10, ge=1, le=50)"
            ),
            source_type=ContextSourceType.SOURCE_CODE,
            language="Python",
            start_line=30,
            end_line=32,
            chunk_type="file_segment",
        ),
        ContextChunk(
            repository_path=str(repository),
            file_path=str(repository / "tests" / "test_invalid_requests.py"),
            relative_path="tests/test_invalid_requests.py",
            content=(
                "def test_invalid_generation_requests():\n"
                "    assert client.post('/tests/generate', "
                "json={'prompt': '', 'count': 51}).status_code == 422"
            ),
            source_type=ContextSourceType.SOURCE_CODE,
            language="Python",
            start_line=1,
            end_line=2,
            chunk_type="file_segment",
        ),
    ]

    class StubRetriever:
        async def retrieve(self, *, session, query):
            captured["query"] = query
            results = (
                []
                if captured.get("no_negative_evidence")
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


def test_negative_only_generation_uses_evidence_and_respects_count(
    negative_generation_client,
    monkeypatch,
):
    client, repository, captured = negative_generation_client

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
                model="negative-test",
                content=_negative_scenarios(),
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
            "prompt": "Generate negative scenarios for invalid generation requests.",
            "test_types": ["negative"],
            "count": 3,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["repository_path"] == str(repository)
    assert result["total_tests"] == len(result["test_cases"]) == 3
    assert all(
        scenario["test_type"] == "negative"
        and scenario["steps"]
        and scenario["expected_result"]
        and scenario["target_file"] == "app/agents/test_generation.py"
        for scenario in result["test_cases"]
    )
    descriptions = " ".join(
        scenario["description"]
        for scenario in result["test_cases"]
    )
    assert "required prompt" in descriptions
    assert "min_length=1" in captured["llm_request"].prompt
    assert "ge=1, le=50" in captured["llm_request"].prompt
    expected_results = " ".join(
        scenario["expected_result"]
        for scenario in result["test_cases"]
    )
    assert "HTTP 422" in expected_results

    query = captured["query"]
    assert query.query == (
        "Generate negative scenarios for invalid generation requests."
    )
    assert query.repository_path == str(repository)
    assert query.top_k == 10

    llm_request = captured["llm_request"]
    assert "Requested test categories:\nnegative" in llm_request.prompt
    assert "Negative scenario instructions" in llm_request.prompt
    assert "invalid or disallowed inputs" in llm_request.prompt
    assert "tests/test_invalid_requests.py" in llm_request.prompt
    assert captured["provider_name"] == "auto"


def test_negative_only_generation_returns_empty_without_negative_evidence(
    negative_generation_client,
    monkeypatch,
):
    client, repository, captured = negative_generation_client
    captured["no_negative_evidence"] = True

    class UnexpectedOrchestrator:
        async def generate(self, **kwargs):
            raise AssertionError(
                "generation must not run without negative-test evidence"
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
            "prompt": "Generate negative scenarios.",
            "test_types": ["negative"],
            "count": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "repository_path": str(repository),
        "test_cases": [],
        "total_tests": 0,
    }


def test_functional_only_generation_does_not_add_negative_guidance(
    negative_generation_client,
    monkeypatch,
):
    client, repository, captured = negative_generation_client

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
        "Identify explicit validation,"
        not in captured["llm_request"].prompt
    )
