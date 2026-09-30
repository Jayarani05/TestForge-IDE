from fastapi import APIRouter

from app.agents.self_healing import (
    SelfHealingRequest,
    SelfHealingResult,
)
from app.services.self_healing_service import (
    SelfHealingService,
)


router = APIRouter(
    prefix="/self-healing",
    tags=["self-healing"],
)

service = SelfHealingService()


@router.post(
    "/repair",
    response_model=SelfHealingResult,
)
async def repair_test(
    request: SelfHealingRequest,
) -> SelfHealingResult:
    return service.repair(request)