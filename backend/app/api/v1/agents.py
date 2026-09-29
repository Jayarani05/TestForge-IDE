from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import (
    AgentRequest,
    AgentResponse,
    TestForgeAgent,
)
from app.agents.context_agent import (
    ContextAwareTestForgeAgent,
)
from app.context import (
    ContextAssembler,
    HashEmbeddingProvider,
    PersistentContextRetriever,
)
from app.context.hybrid_retriever import (
    HybridContextRetriever,
)
from app.core.database import get_db


router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


base_agent = TestForgeAgent()


embedding_provider = HashEmbeddingProvider(
    dimension=128,
)


persistent_retriever = PersistentContextRetriever(
    embedding_provider=embedding_provider,
)


hybrid_retriever = HybridContextRetriever(
    vector_retriever=persistent_retriever,
)


context_assembler = ContextAssembler()


agent = ContextAwareTestForgeAgent(
    agent=base_agent,
    retriever=hybrid_retriever,
    assembler=context_assembler,
)


@router.post(
    "/execute",
    response_model=AgentResponse,
)
async def execute_agent(
    request: AgentRequest,
    session: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """
    Execute a repository-aware TestForge AI task.
    """

    try:
        return await agent.execute(
            session=session,
            request=request,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Agent execution failed.",
        ) from exc