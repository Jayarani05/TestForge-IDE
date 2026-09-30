from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.execution.models import ExecutionFramework
from app.services.intelligent_testing_service import (
    IntelligentTestingService,
)


router = APIRouter(
    prefix="/intelligent-testing",
    tags=["intelligent-testing"],
)

service = IntelligentTestingService()


class IntelligentTestingRequest(BaseModel):
    repository_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    framework: ExecutionFramework = ExecutionFramework.PYTEST
    timeout_seconds: int = Field(
        default=120,
        ge=1,
        le=3600,
    )
    args: list[str] = Field(default_factory=list)
    source_code: str = ""


@router.post("/run")
async def run_intelligent_testing(
    request: IntelligentTestingRequest,
) -> dict:

    return await service.execute_and_analyze(
        repository_path=request.repository_path,
        file_path=request.file_path,
        framework=request.framework,
        timeout_seconds=request.timeout_seconds,
        args=request.args,
        source_code=request.source_code,
    )