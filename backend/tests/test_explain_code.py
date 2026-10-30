import asyncio

from app.agents import AgentRequest, AgentTask, TestForgeAgent
from app.agents.orchestrator import LLMOrchestrator
from app.agents.provider_registry import LLMProviderRegistry
from app.agents.providers import MockLLMProvider


def test_explain_code_task_is_supported():
    assert AgentTask.EXPLAIN_CODE.value == "explain_code"


def test_explain_code_agent_uses_mock_provider_without_executing_code():
    registry = LLMProviderRegistry()
    registry.register(MockLLMProvider())
    agent = TestForgeAgent(orchestrator=LLMOrchestrator(registry=registry))

    response = asyncio.run(
        agent.execute(
            AgentRequest(
                task=AgentTask.EXPLAIN_CODE,
                prompt="def add(a, b): return a + b",
                provider="mock",
            )
        )
    )

    assert response.task == AgentTask.EXPLAIN_CODE
    assert response.provider == "mock"
    assert response.content