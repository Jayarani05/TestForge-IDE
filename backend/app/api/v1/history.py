from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.history_schemas import (
    AnalyticsHistoryItem,
    ExecutionHistoryItem,
    FailureHistoryItem,
    SelfHealingHistoryItem,
)
from app.services.history_service import testing_history_service


router = APIRouter(
    prefix="/history",
    tags=["history"],
)


@router.get(
    "/executions",
    response_model=list[ExecutionHistoryItem],
)
async def get_execution_history(
    repository_path: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    records = await testing_history_service.executions(
        db,
        repository_path,
        limit,
    )

    return [
        ExecutionHistoryItem.model_validate(record, from_attributes=True)
        for record in records
    ]


@router.get(
    "/failures",
    response_model=list[FailureHistoryItem],
)
async def get_failure_history(
    repository_path: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    records = await testing_history_service.failures(
        db,
        repository_path,
        limit,
    )

    return [
        FailureHistoryItem.model_validate(record, from_attributes=True)
        for record in records
    ]


@router.get(
    "/self-healing",
    response_model=list[SelfHealingHistoryItem],
)
async def get_self_healing_history(
    repository_path: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    records = await testing_history_service.self_healing(
        db,
        repository_path,
        limit,
    )

    return [
        SelfHealingHistoryItem.model_validate(record, from_attributes=True)
        for record in records
    ]


@router.get(
    "/analytics",
    response_model=list[AnalyticsHistoryItem],
)
async def get_analytics_history(
    repository_path: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    records = await testing_history_service.analytics(
        db,
        repository_path,
        limit,
    )

    return [
        AnalyticsHistoryItem.model_validate(record, from_attributes=True)
        for record in records
    ]
