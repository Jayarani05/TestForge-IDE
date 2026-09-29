from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import (
    ContextChunkingService,
    ContextEmbeddingService,
    HashEmbeddingProvider,
)
from app.core.database import get_db
from app.repository.schemas import RepositoryImportRequest


router = APIRouter(
    prefix="/context",
    tags=["Context"],
)

chunking_service = ContextChunkingService()

embedding_service = ContextEmbeddingService(
    embedding_provider=HashEmbeddingProvider(
        dimension=128,
    )
)


@router.post("/index")
async def index_repository_context(
    request: RepositoryImportRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Chunk a repository, generate embeddings, and persist them."""

    try:
        chunks = chunking_service.chunk_repository(
            request.path
        )

        indexed_count = await embedding_service.index_chunks(
            session=session,
            chunks=chunks,
        )

        return {
            "status": "ok",
            "repository_path": request.path,
            "chunks_created": len(chunks),
            "chunks_indexed": indexed_count,
            "embedding_dimension": (
                embedding_service.embedding_provider.dimension
            ),
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=(
                "Permission denied while indexing "
                "repository context."
            ),
        ) from exc