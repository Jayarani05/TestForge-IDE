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


SCENARIO_EVIDENCE = {
    "exception": (
        "def load_config(path):\n"
        "    try:\n"
        "        return read_config(path)\n"
        "    except OSError as exc:\n"
        "        raise ValueError('Unable to load config') from exc\n"
        "\n"
        "def test_load_config_wraps_os_error():\n"
        "    with pytest.raises(ValueError):\n"
        "        load_config('missing.toml')"
    ),
    "edge_case": (
        "def get_user(user_id, cache=None):\n"
        "    if user_id is None or not user_id:\n"
        "        return None\n"
        "    if cache is not None and user_id in cache:\n"
        "        return cache[user_id]\n"
        "    return load_user(user_id)"
    ),
}


def _scenario_response(test_type: str) -> str:
    return json.dumps(
        {
            "test_cases": [
                {
                    "id": f"TC-{test_type.upper()}-001",
                    "title": f"Verify documented {test_type} behavior",
                    "description": (
                        f"Exercise the repository-evidenced {test_type} path."
                    ),
                    "test_type": test_type,
                    "priority": "high",
                    "preconditions": ["The test fixture is configured."],
                    "steps": [
                        "Arrange the evidenced condition.",
                        "Execute the relevant function.",
                        "Inspect the observable outcome.",
                    ],
                    "expected_result": (
                        "The documented behavior for this condition occurs."
                    ),
                    "target_file": "src/config.py",
                    "target_function": "load_config",
                },
                {
                    "id": "TC-FUNC-001",
                    "title": "Unrequested functional case",
                    "description": "Unrequested scenario type.",
                    "test_type": "functional",
                    "priority": "medium",
                    "preconditions": [],
                    "steps": ["Run the function."],
                    "expected_result": "The function returns.",
                    "target_file": None,
                    "target_function": None,
                },
            ]
        }
    )


@pytest.fixture
def exception_edge_client(monkeypatch, tmp_path):
    repository = tmp_path / "exception-edge-repository"
    repository.mkdir()
    captured: dict[str, object] = {}

    class StubRetriever:
        async def retrieve(self, *, session, query):
            captured["query"] = query
            content = (
                ""
                if captured.get("no_evidence")
                else str(
                    captured.get(
                        "context_override",
                        SCENARIO_EVIDENCE[
                            str(captured.get("scenario_type", "exception"))
                        ],
                    )
                )
            )
            chunks = []
            if content:
                chunks.append(
                    ContextResult(
                        chunk=ContextChunk(
                            repository_path=str(repository),
                            file_path=str(repository / "src" / "config.py"),
                            relative_path="src/config.py",
                            content=content,
                            source_type=ContextSourceType.SOURCE_CODE,
                            language="Python",
                            start_line=1,
                            end_line=len(content.splitlines()),
                            chunk_type="file_segment",
                        ),
                        score=0.9,
                    )
                )
            return ContextResponse(
                query=query.query,
                repository_path=str(repository),
                results=chunks,
                total_results=len(chunks),
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


@pytest.mark.parametrize(
    ("test_type", "required_prompt", "evidence_fragment"),
    [
        ("exception", "exception propagation", "pytest.raises"),
        ("edge_case", "optional states", "user_id is None"),
    ],
)
def test_exception_and_edge_case_only_generation_uses_context(
    exception_edge_client,
    monkeypatch,
    test_type,
    required_prompt,
    evidence_fragment,
):
    client, repository, captured = exception_edge_client
    captured["scenario_type"] = test_type

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
                model=f"{test_type}-test",
                content=_scenario_response(test_type),
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
            "prompt": f"Verify {test_type} behavior.",
            "test_types": [test_type],
            "count": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["repository_path"] == str(repository)
    assert result["total_tests"] == len(result["test_cases"]) == 1
    scenario = result["test_cases"][0]
    assert scenario["test_type"] == test_type
    assert scenario["steps"]
    assert scenario["expected_result"]

    query = captured["query"]
    assert query.repository_path == str(repository)
    assert query.query == f"Verify {test_type} behavior."
    assert query.top_k == 10

    llm_request = captured["llm_request"]
    assert f"Requested test categories:\n{test_type}" in llm_request.prompt
    assert evidence_fragment in llm_request.prompt
    assert required_prompt in llm_request.prompt.lower()


@pytest.mark.parametrize("test_type", ["exception", "edge_case"])
def test_exception_and_edge_case_requests_return_empty_without_evidence(
    exception_edge_client,
    monkeypatch,
    test_type,
):
    client, repository, captured = exception_edge_client
    captured["scenario_type"] = test_type
    captured["no_evidence"] = True

    class UnexpectedOrchestrator:
        async def generate(self, **kwargs):
            raise AssertionError(
                "generation must not run without matching repository evidence"
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
            "prompt": f"Generate {test_type} scenarios.",
            "test_types": [test_type],
            "count": 2,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "repository_path": str(repository),
        "test_cases": [],
        "total_tests": 0,
    }


@pytest.mark.parametrize("count", [0, 51])
def test_generation_rejects_counts_outside_existing_limits(
    exception_edge_client,
    count,
):
    client, repository, _ = exception_edge_client
    response = client.post(
        "/tests/generate",
        json={
            "repository_path": str(repository),
            "prompt": "Validate the existing count limit.",
            "test_types": ["exception"],
            "count": count,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("count", [1, 50])
def test_generation_accepts_existing_minimum_and_maximum_counts(
    exception_edge_client,
    monkeypatch,
    count,
):
    client, repository, captured = exception_edge_client

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
                model="count-boundary-test",
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
            "prompt": "Validate the supported count.",
            "test_types": ["functional"],
            "count": count,
        },
    )

    assert response.status_code == 200
    assert response.json()["total_tests"] == 0
    assert f"Generate {count} test cases." in (
        captured["llm_request"].prompt
    )


@pytest.mark.parametrize(
    ("requested_type", "evidence_type"),
    [
        ("exception", "edge_case"),
        ("edge_case", "exception"),
    ],
)
def test_exception_and_edge_case_evidence_do_not_cross_categories(
    exception_edge_client,
    monkeypatch,
    requested_type,
    evidence_type,
):
    client, repository, captured = exception_edge_client
    captured["scenario_type"] = requested_type
    captured["context_override"] = SCENARIO_EVIDENCE[evidence_type]

    class UnexpectedOrchestrator:
        async def generate(self, **kwargs):
            raise AssertionError(
                "evidence from another scenario category is insufficient"
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
            "prompt": f"Generate {requested_type} scenarios.",
            "test_types": [requested_type],
            "count": 2,
        },
    )

    assert response.status_code == 200
    assert response.json()["test_cases"] == []
