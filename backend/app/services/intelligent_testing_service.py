from app.agents.failure_analysis import FailureAnalysisRequest
from app.core.database import AsyncSessionLocal
from app.execution.models import ExecutionFramework, ExecutionStatus
from app.execution.playwright_executor import PlaywrightExecutor
from app.execution.pytest_executor import PytestExecutor
from app.execution.selenium_executor import SeleniumExecutor
from app.services.failure_analysis_service import FailureAnalysisService
from app.services.testing_persistence_service import testing_persistence_service


class IntelligentTestingService:
    def __init__(self) -> None:
        self.pytest_executor = PytestExecutor()
        self.playwright_executor = PlaywrightExecutor()
        self.selenium_executor = SeleniumExecutor()
        self.failure_analyzer = FailureAnalysisService()

    async def _persist_pipeline(
        self,
        execution,
        failure_analysis,
    ) -> None:
        async with AsyncSessionLocal() as db:
            await testing_persistence_service.save_execution(
                db,
                execution,
            )
            if failure_analysis is not None:
                await testing_persistence_service.save_failure_analysis(
                    db,
                    execution,
                    failure_analysis,
                )
            await testing_persistence_service.commit(db)

    async def _execute(
        self,
        repository_path: str,
        file_path: str,
        framework: ExecutionFramework,
        timeout_seconds: int,
        args: list[str] | None,
    ):
        if framework == ExecutionFramework.PYTEST:
            return await self.pytest_executor.execute(
                repository_path=repository_path,
                file_path=file_path,
                timeout_seconds=timeout_seconds,
                args=args,
            )
        if framework == ExecutionFramework.PLAYWRIGHT:
            return await self.playwright_executor.execute(
                repository_path=repository_path,
                file_path=file_path,
                timeout_seconds=timeout_seconds,
                args=args,
            )
        if framework == ExecutionFramework.SELENIUM:
            return await self.selenium_executor.execute(
                repository_path=repository_path,
                file_path=file_path,
                timeout_seconds=timeout_seconds,
                args=args,
            )
        raise ValueError(f"Unsupported execution framework: {framework}")

    async def execute_and_analyze(
        self,
        repository_path: str,
        file_path: str,
        framework: ExecutionFramework,
        timeout_seconds: int = 120,
        args: list[str] | None = None,
        source_code: str = "",
    ) -> dict:
        execution = await self._execute(
            repository_path=repository_path,
            file_path=file_path,
            framework=framework,
            timeout_seconds=timeout_seconds,
            args=args,
        )
        failure_analysis = None
        if execution.status not in {
            ExecutionStatus.PASSED,
            ExecutionStatus.SKIPPED,
        }:
            failure_analysis = self.failure_analyzer.analyze(
                FailureAnalysisRequest(execution=execution)
            )

        await self._persist_pipeline(execution, failure_analysis)
        return {
            "execution": execution.model_dump(),
            "failure_analysis": (
                failure_analysis.model_dump()
                if failure_analysis is not None
                else None
            ),
            "self_healing": None,
            "re_execution": None,
            "analytics": None,
        }
