from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import TestForgeAgent
from app.agents.schemas import AgentRequest, AgentResponse
from app.context import (
    ContextAssembler,
    ContextQuery,
)
from app.context.hybrid_retriever import (
    HybridContextRetriever,
)


class ContextAwareTestForgeAgent:
    """
    TestForge agent that automatically retrieves
    repository-aware context before executing an AI task.
    """

    def __init__(
        self,
        agent: TestForgeAgent,
        retriever: HybridContextRetriever,
        assembler: ContextAssembler,
    ) -> None:
        self.agent = agent
        self.retriever = retriever
        self.assembler = assembler

    async def execute(
        self,
        session: AsyncSession,
        request: AgentRequest,
    ) -> AgentResponse:

        if not request.repository_path:
            return await self.agent.execute(
                request
            )

        query = ContextQuery(
            query=request.prompt,
            repository_path=request.repository_path,
            top_k=10,
        )

        retrieval_response = (
            await self.retriever.retrieve(
                session=session,
                query=query,
            )
        )

        assembly = self.assembler.assemble(
            query=request.prompt,
            repository_path=request.repository_path,
            results=retrieval_response.results,
        )

        context_text = self._format_context(
            assembly
        )

        enriched_request = request.model_copy(
            update={
                "context": context_text,
            }
        )

        return await self.agent.execute(
            enriched_request
        )

    @staticmethod
    def _format_context(
        assembly,
    ) -> str:

        sections: list[str] = []

        for chunk in assembly.chunks:
            header = (
                f"File: {chunk.relative_path}\n"
                f"Lines: "
                f"{chunk.start_line}-"
                f"{chunk.end_line}\n"
            )

            sections.append(
                header
                + chunk.content
            )

        return "\n\n".join(sections)