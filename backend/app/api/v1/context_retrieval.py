from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import (
    ContextQuery,
    ContextResponse,
    HashEmbeddingProvider,
    PersistentContextRetriever,
)
from app.core.database import get_db


router = APIRouter(
    prefix="/context",
    tags=["Context"],
)


embedding_provider = HashEmbeddingProvider(
    dimension=128,
)

retriever = PersistentContextRetriever(
    embedding_provider=embedding_provider,
)


@router.post(
    "/retrieve",
    response_model=ContextResponse,
)
async def retrieve_context(
    query: ContextQuery,
    session: AsyncSession = Depends(get_db),
) -> ContextResponse:
    """Retrieve relevant persisted repository context."""

    try:
        return await retriever.retrieve(
            session=session,
            query=query,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc