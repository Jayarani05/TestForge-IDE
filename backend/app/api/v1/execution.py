import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.execution.models import ExecutionFramework, ExecutionRequest, ExecutionResult
from app.execution.result_registry import execution_result_registry
from app.execution.playwright_executor import PlaywrightExecutor
from app.execution.pytest_executor import PytestExecutor
from app.execution.selenium_executor import SeleniumExecutor
from app.services.testing_persistence_service import testing_persistence_service


router = APIRouter(
    prefix="/execution",
    tags=["execution"],
)

logger = logging.getLogger(__name__)

pytest_executor = PytestExecutor()
playwright_executor = PlaywrightExecutor()
selenium_executor = SeleniumExecutor()


@router.post(
    "/run",
    response_model=ExecutionResult,
)
async def run_test(
    request: ExecutionRequest,
    db: AsyncSession = Depends(get_db),
) -> ExecutionResult:
    try:
        if request.framework == ExecutionFramework.PYTEST:
            result = await pytest_executor.execute(
                repository_path=request.repository_path,
                file_path=request.file_path,
                timeout_seconds=request.timeout_seconds,
                args=request.args,
                measure_coverage=request.measure_coverage,
            )
        elif request.framework == ExecutionFramework.PLAYWRIGHT:
            result = await playwright_executor.execute(
                repository_path=request.repository_path,
                file_path=request.file_path,
                timeout_seconds=request.timeout_seconds,
                args=request.args,
                measure_coverage=request.measure_coverage,
            )
        elif request.framework == ExecutionFramework.SELENIUM:
            result = await selenium_executor.execute(
                repository_path=request.repository_path,
                file_path=request.file_path,
                timeout_seconds=request.timeout_seconds,
                args=request.args,
                measure_coverage=request.measure_coverage,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported execution framework: {request.framework.value}",
            )
        validated_result = ExecutionResult.model_validate(result)
        if (
            request.measure_coverage
            and validated_result.coverage_percent is None
            and validated_result.coverage_error is None
        ):
            reason = (
                "Coverage measurement is not available for the Playwright runner."
                if request.framework == ExecutionFramework.PLAYWRIGHT
                else "Coverage measurement could not be collected by the test runner."
            )
            validated_result = validated_result.model_copy(
                update={"coverage_error": reason}
            )
        await testing_persistence_service.save_execution(db, validated_result)
        await testing_persistence_service.commit(db)
        execution_result_registry.store(validated_result)
        return validated_result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("Test execution or persistence failed.")
        raise HTTPException(
            status_code=500,
            detail="Test execution could not be completed.",
        ) from exc