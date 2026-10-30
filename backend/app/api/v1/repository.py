from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repository.file_tree import RepositoryTree
from app.repository.tree_service import RepositoryTreeService
from app.repository.schemas import (
    RepositoryImportRequest,
    RepositoryInfo,
)
from app.repository.analyzer import RepositoryAnalysis
from app.repository.analyzer_service import RepositoryAnalyzerService
from app.repository.service import RepositoryService
from app.repository.tree_service import RepositoryTreeService


router = APIRouter(
    prefix="/repository",
    tags=["Repository"],
)

repository_service = RepositoryService()
tree_service = RepositoryTreeService()
repository_analyzer = RepositoryAnalyzerService()


@router.post(
    "/analyze",
    response_model=RepositoryAnalysis,
)
def analyze_repository(
    request: RepositoryImportRequest,
) -> RepositoryAnalysis:
    try:
        return repository_analyzer.analyze_repository(
            request.path
        )

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
            detail="Permission denied while analyzing the repository.",
        ) from exc


@router.post(
    "/inspect",
    response_model=RepositoryInfo,
)
async def inspect_repository(
    request: RepositoryImportRequest,
    session: AsyncSession = Depends(get_db),
) -> RepositoryInfo:
    """
    Inspect a local repository and persist its metadata.
    """

    try:
        repository_info = repository_service.inspect_repository(
            request.path
        )

        await repository_service.save_repository(
            session,
            repository_info,
        )

        return repository_info

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
            detail="Permission denied while accessing the repository.",
        ) from exc


@router.get(
    "/tree",
    response_model=RepositoryTree,
)
async def get_repository_tree(
    path: str,
) -> RepositoryTree:
    """
    Scan a repository and return its file and directory metadata.
    """

    try:
        return tree_service.scan_repository(path)

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
            detail="Permission denied while accessing the repository.",
        ) from exc