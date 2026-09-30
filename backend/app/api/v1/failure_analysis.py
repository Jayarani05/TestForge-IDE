from fastapi import APIRouter

from app.agents.failure_analysis import (
    FailureAnalysisRequest,
    FailureAnalysisResult,
)
from app.services.failure_analysis_service import (
    FailureAnalysisService,
)


router = APIRouter(
    prefix="/failure-analysis",
    tags=["failure-analysis"],
)

service = FailureAnalysisService()


@router.post(
    "/analyze",
    response_model=FailureAnalysisResult,
)
async def analyze_failure_endpoint(
    request: FailureAnalysisRequest,
) -> FailureAnalysisResult:
    return service.analyze(request)