from fastapi import APIRouter

from app.analytics.models import (
    AnalyticsRecord,
    AnalyticsResponse,
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
    record: AnalyticsRecord,
) -> AnalyticsResponse:
    return service.calculate(record)