from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import (
    ContextAssembler,
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


assembler = ContextAssembler()


@router.post("/assemble")
async def assemble_context(
    query: ContextQuery,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """
    Retrieve relevant repository context and assemble
    it into an LLM-ready context package.
    """

    try:
        retrieval_response = (
            await hybrid_retriever.retrieve(
                session=session,
                query=query,
            )
        )

        assembly = assembler.assemble(
            query=query.query,
            repository_path=query.repository_path,
            results=retrieval_response.results,
        )

        return {
            "status": "ok",
            "query": assembly.query,
            "repository_path": assembly.repository_path,
            "total_chunks": assembly.total_chunks,
            "estimated_tokens": assembly.estimated_tokens,
            "chunks": [
                {
                    "relative_path": chunk.relative_path,
                    "file_path": chunk.file_path,
                    "source_type": chunk.source_type.value,
                    "language": chunk.language,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "content": chunk.content,
                }
                for chunk in assembly.chunks
            ],
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc