from fastapi import APIRouter

from app.analytics.models import (
    AnalyticsRecord,
    AnalyticsResponse,
    SelfHealingMetricRequest,
    SelfHealingMetricResponse,
)
from app.analytics.service import AnalyticsService


router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
)

service = AnalyticsService()


@router.post(
    "/calculate",
    response_model=AnalyticsResponse,
)
async def calculate_analytics(
    request: AnalyticsRecord,
) -> AnalyticsResponse:
    return service.calculate(request)


@router.post(
    "/self-healing",
    response_model=SelfHealingMetricResponse,
)
async def calculate_self_healing_metric(
    request: SelfHealingMetricRequest,
) -> SelfHealingMetricResponse:
    return service.calculate_self_healing_metric(request)