import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.failure_analysis import (
    FailureAnalysisRequest,
    FailureAnalysisResult,
)
from app.core.database import get_db
from app.services.failure_analysis_service import (
    FailureAnalysisService,
)
from app.execution.result_registry import execution_result_registry
from app.services.testing_persistence_service import testing_persistence_service


router = APIRouter(
    prefix="/failure-analysis",
    tags=["failure-analysis"],
)

service = FailureAnalysisService()
logger = logging.getLogger(__name__)


@router.post(
    "/analyze",
    response_model=FailureAnalysisResult,
)
async def analyze_failure_endpoint(
    request: FailureAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> FailureAnalysisResult:
    try:
        recorded = execution_result_registry.get(request.execution.execution_id)
        if recorded is None or recorded != request.execution:
            raise HTTPException(
                status_code=409,
                detail="Failure analysis must reference a recent execution result.",
            )
        result = service.analyze(request)
        await testing_persistence_service.save_failure_analysis(
            db,
            request.execution,
            result,
        )
        await testing_persistence_service.commit(db)
        return result
    except HTTPException:
        raise
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failure analysis request failed.")
        raise HTTPException(
            status_code=500,
            detail="Failure analysis could not be completed.",
        ) from exc