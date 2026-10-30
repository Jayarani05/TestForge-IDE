import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.self_healing import (
    RepairApplyRequest,
    RepairOperationResult,
    SelfHealingRequest,
    SelfHealingResult,
)
from app.core.database import get_db
from app.services.self_healing_service import (
    SelfHealingService,
)
from app.execution.result_registry import execution_result_registry
from app.api.v1.failure_analysis import service as failure_analysis_service
from app.services.testing_persistence_service import testing_persistence_service


router = APIRouter(
    prefix="/self-healing",
    tags=["self-healing"],
)

service = SelfHealingService()
logger = logging.getLogger(__name__)


@router.post(
    "/repair",
    response_model=SelfHealingResult,
)
async def repair_test(
    request: SelfHealingRequest,
    db: AsyncSession = Depends(get_db),
) -> SelfHealingResult:
    try:
        recorded = execution_result_registry.get(request.execution.execution_id)
        if recorded is None or recorded != request.execution:
            raise HTTPException(
                status_code=409,
                detail="Repair candidates require a recent execution result.",
            )
        recorded_analysis = failure_analysis_service.get_recorded(request.execution)
        if recorded_analysis is None or recorded_analysis != request.analysis:
            raise HTTPException(
                status_code=409,
                detail="Repair candidates require analysis of this execution.",
            )
        candidate = await service.repair(request)
        await testing_persistence_service.save_repair_candidate(
            db,
            request.execution,
            request.analysis,
            candidate,
        )
        await testing_persistence_service.commit(db)
        return candidate
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Repair candidate generation failed.")
        raise HTTPException(
            status_code=502,
            detail="Repair candidate generation could not be completed.",
        ) from exc


@router.post(
    "/apply",
    response_model=RepairOperationResult,
)
async def apply_repair(
    request: RepairApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> RepairOperationResult:
    try:
        stored = await testing_persistence_service.get_repair(db, request.repair_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Repair candidate was not found.")
        result = service.apply(request.repair_id, request.approved)
        await testing_persistence_service.record_repair_applied(
            db,
            request.repair_id,
            approved=request.approved,
            outcome=result.message,
        )
        await testing_persistence_service.commit(db)
        return result
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Repair was applied but its lifecycle record could not be persisted.")
        raise HTTPException(
            status_code=500,
            detail="Repair may have been applied, but its outcome could not be persisted.",
        ) from exc


@router.post(
    "/restore",
    response_model=RepairOperationResult,
)
async def restore_repair(
    request: RepairApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> RepairOperationResult:
    if not request.approved:
        raise HTTPException(
            status_code=400,
            detail="Explicit approval is required to restore a repair.",
        )
    try:
        stored = await testing_persistence_service.get_repair(db, request.repair_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Repair candidate was not found.")
        result = service.restore(request.repair_id)
        await testing_persistence_service.record_repair_restored(
            db,
            request.repair_id,
            approved=request.approved,
            outcome=result.message,
        )
        await testing_persistence_service.commit(db)
        return result
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Repair was restored but its lifecycle record could not be persisted.")
        raise HTTPException(
            status_code=500,
            detail="Repair was restored, but its outcome could not be persisted.",
        ) from exc