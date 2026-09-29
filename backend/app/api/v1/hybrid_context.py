from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import (
    ContextQuery,
    ContextResponse,
    HashEmbeddingProvider,
    PersistentContextRetriever,
)
from app.context.hybrid_retriever import (
    HybridContextRetriever,
)
from app.core.database import get_db


router = APIRouter(
    prefix="/context",
    tags=["Context"],
)


embedding_provider = HashEmbeddingProvider(
    dimension=128,
)


persistent_retriever = PersistentContextRetriever(
    embedding_provider=embedding_provider,
)


hybrid_retriever = HybridContextRetriever(
    vector_retriever=persistent_retriever,
)


@router.post(
    "/hybrid-retrieve",
    response_model=ContextResponse,
)
async def retrieve_hybrid_context(
    query: ContextQuery,
    session: AsyncSession = Depends(get_db),
) -> ContextResponse:
    """
    Retrieve repository context using hybrid
    lexical and vector retrieval.
    """

    try:
        return await hybrid_retriever.retrieve(
            session=session,
            query=query,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc