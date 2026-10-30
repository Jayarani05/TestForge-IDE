from collections.abc import AsyncGenerator
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import TestForgeAgent as RealAgent
from app.agents.providers.base import LLMResponse
from app.agents.schemas import AgentResponse
from app.api.v1 import agents as agents_api
from app.context.models import (
    ContextChunk,
    ContextResponse,
    ContextResult,
    ContextSourceType,
)
from app.core.database import get_db
from app.main import app


def test_agents_endpoint_passes_retrieved_context_to_agent(
    tmp_path,
    monkeypatch,
):
    repository = (tmp_path / "repository").resolve()
    relative_repository_path = os.path.relpath(
        repository,
        Path.cwd(),
    )
    session = SimpleNamespace()
    received: dict[str, object] = {}
    chunk = ContextChunk(
        repository_path=str(repository),
        file_path=str(repository / "src" / "service.py"),
        relative_path="src/service.py",
        content="def service(): return 'context'",
        source_type=ContextSourceType.SOURCE_CODE,
        language="Python",
        start_line=3,
        end_line=3,
        chunk_type="file_segment",
    )

    class StubRetriever:
        async def retrieve(self, *, session, query):
            received["query"] = query
            return ContextResponse(
                query=query.query,
                repository_path=str(repository),
                results=[
                    ContextResult(chunk=chunk, score=0.9)
                ],
                total_results=1,
            )

    class StubOrchestrator:
        async def generate(
            self,
            *,
            request,
            provider_name,
            fallback_providers,
        ):
            received["llm_request"] = request
            received["provider_name"] = provider_name
            received["fallback_providers"] = fallback_providers
            return LLMResponse(
                provider="mock",
                model="test",
                content="generated response",
            )

    monkeypatch.setattr(
        agents_api.agent,
        "retriever",
        StubRetriever(),
    )
    monkeypatch.setattr(
        agents_api.agent,
        "agent",
        RealAgent(orchestrator=StubOrchestrator()),
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/agents/execute",
                json={
                    "task": "generate_tests",
                    "prompt": "Generate service tests",
                    "provider": "mock",
                    "fallback_providers": [],
                    "repository_path": relative_repository_path,
                    "temperature": 0.2,
                    "max_tokens": 4096,
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert received["query"].query == "Generate service tests"
    assert (
        received["query"].repository_path
        == relative_repository_path
    )
    assert received["query"].top_k == 10
    llm_request = received["llm_request"]
    assert "TestForge Task: generate_tests" in llm_request.prompt
    assert "User Request:\nGenerate service tests" in llm_request.prompt
    assert f"Repository:\n{repository}" in llm_request.prompt
    assert "Repository Context:\n" in llm_request.prompt
    assert (
        "File: src/service.py\n"
        "Lines: 3-3\n"
        "def service(): return 'context'"
    ) in llm_request.prompt
    assert received["provider_name"] == "mock"
    assert response.json()["task"] == "generate_tests"
    assert response.json()["provider"] == "mock"
    assert response.json()["model"] == "test"
    assert response.json()["content"] == "generated response"


def test_agents_endpoint_executes_without_repository_context(
    monkeypatch,
):
    received: dict[str, object] = {}

    class UnexpectedRetriever:
        async def retrieve(self, *, session, query):
            raise AssertionError(
                "retrieval should be skipped without a repository"
            )

    class StubAgent:
        async def execute(self, request):
            received["request"] = request
            return AgentResponse(
                task=request.task,
                provider="mock",
                model="test",
                content="generated without repository context",
            )

    monkeypatch.setattr(
        agents_api.agent,
        "retriever",
        UnexpectedRetriever(),
    )
    monkeypatch.setattr(
        agents_api.agent,
        "agent",
        StubAgent(),
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/agents/execute",
                json={
                    "task": "generate_tests",
                    "prompt": "Generate general test scenarios",
                    "provider": "mock",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert received["request"].repository_path is None
    assert received["request"].context is None
    assert response.json() == {
        "task": "generate_tests",
        "provider": "mock",
        "model": "test",
        "content": "generated without repository context",
        "input_tokens": None,
        "output_tokens": None,
        "analysis": None,
    }


def test_agents_endpoint_returns_not_found_for_missing_analysis_repository(
    tmp_path,
    monkeypatch,
):
    repository = tmp_path / "missing"

    class EmptyRetriever:
        async def retrieve(self, *, session, query):
            return ContextResponse(
                query=query.query,
                repository_path=query.repository_path,
                results=[],
                total_results=0,
            )

    class StubOrchestrator:
        async def generate(
            self,
            *,
            request,
            provider_name,
            fallback_providers,
        ):
            return LLMResponse(
                provider="mock",
                model="test",
                content="analysis response",
            )

    monkeypatch.setattr(
        agents_api.agent,
        "retriever",
        EmptyRetriever(),
    )
    monkeypatch.setattr(
        agents_api.agent.agent,
        "orchestrator",
        StubOrchestrator(),
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/agents/execute",
                json={
                    "task": "analyze_repository",
                    "prompt": "Analyze this repository",
                    "provider": "mock",
                    "repository_path": str(repository),
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Repository path does not exist."
    )


def test_agents_endpoint_does_not_expose_provider_exception_details(
    monkeypatch,
):
    class StubOrchestrator:
        async def generate(
            self,
            *,
            request,
            provider_name,
            fallback_providers,
        ):
            raise RuntimeError(
                "provider failure with secret-token-value"
            )

    monkeypatch.setattr(
        agents_api.agent.agent,
        "orchestrator",
        StubOrchestrator(),
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/agents/execute",
                json={
                    "task": "generate_tests",
                    "prompt": "Generate tests",
                    "provider": "mock",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.json()["detail"] == "Agent execution failed."
    assert "secret-token-value" not in response.text


def test_agents_endpoint_maps_context_permission_failure(
    monkeypatch,
):
    class DeniedRetriever:
        async def retrieve(self, *, session, query):
            raise PermissionError("private filesystem detail")

    monkeypatch.setattr(
        agents_api.agent,
        "retriever",
        DeniedRetriever(),
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/agents/execute",
                json={
                    "task": "generate_tests",
                    "prompt": "Generate tests",
                    "provider": "mock",
                    "repository_path": "repository",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission denied while accessing repository context."
    )
    assert "private filesystem detail" not in response.text


def test_agents_endpoint_rejects_missing_required_fields():
    with TestClient(app) as client:
        response = client.post(
            "/agents/execute",
            json={"task": "generate_tests"},
        )

    assert response.status_code == 422
