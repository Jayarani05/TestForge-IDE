from app.agents.orchestrator import LLMOrchestrator
from app.agents.providers import LLMRequest
from app.agents.routing import LLMRoutingStrategy
from app.agents.schemas import (
    AgentRequest,
    AgentResponse,
)


class TestForgeAgent:
    """
    Main AI agent for TestForge testing workflows.
    """

    def __init__(
        self,
        orchestrator: LLMOrchestrator | None = None,
    ) -> None:
        self.orchestrator = (
            orchestrator
            or LLMOrchestrator()
        )

    async def execute(
        self,
        request: AgentRequest,
    ) -> AgentResponse:
        prompt = self._build_prompt(request)

        llm_request = LLMRequest(
            prompt=prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        route = LLMRoutingStrategy.get_route(
            request.task
        )

        if request.provider != "auto":
            provider = request.provider

            fallback_providers = [
                name
                for name in route
                if name != provider
            ]
        else:
            provider = route[0]

            fallback_providers = route[1:]

        if request.fallback_providers:
            fallback_providers = (
                request.fallback_providers
                + fallback_providers
            )

        response = await self.orchestrator.generate(
            request=llm_request,
            provider_name=provider,
            fallback_providers=fallback_providers,
        )

        return AgentResponse(
            task=request.task,
            provider=response.provider,
            model=response.model,
            content=response.content,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    @staticmethod
    def _build_prompt(
        request: AgentRequest,
    ) -> str:
        sections: list[str] = []

        sections.append(
            f"TestForge Task: {request.task.value}"
        )

        sections.append(
            f"User Request:\n{request.prompt}"
        )

        if request.repository_path:
            sections.append(
                "Repository:\n"
                f"{request.repository_path}"
            )

        if request.context:
            sections.append(
                "Repository Context:\n"
                f"{request.context}"
            )

        sections.append(
            "Provide a precise response suitable "
            "for the TestForge testing workflow."
        )

        return "\n\n".join(sections)