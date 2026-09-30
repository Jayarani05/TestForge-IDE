from app.agents.failure_analysis import FailureAnalysisRequest
from app.agents.self_healing import SelfHealingRequest
from app.agents.code_validator import GeneratedCodeValidator
from app.execution.models import (
    ExecutionFramework,
    ExecutionStatus,
)
from app.execution.playwright_executor import PlaywrightExecutor
from app.execution.pytest_executor import PytestExecutor
from app.execution.selenium_executor import SeleniumExecutor
from app.services.failure_analysis_service import FailureAnalysisService
from app.services.repair_file_service import RepairFileService
from app.services.self_healing_service import SelfHealingService


class IntelligentTestingService:

    def __init__(self) -> None:
        self.pytest_executor = PytestExecutor()
        self.playwright_executor = PlaywrightExecutor()
        self.selenium_executor = SeleniumExecutor()

        self.failure_analyzer = FailureAnalysisService()
        self.self_healing = SelfHealingService()
        self.repair_files = RepairFileService()
        self.code_validator = GeneratedCodeValidator()

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

        raise ValueError(
            f"Unsupported execution framework: {framework}"
        )

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

        result = {
            "execution": execution.model_dump(),
            "failure_analysis": None,
            "self_healing": None,
            "re_execution": None,
        }

        # Test passed on the first execution.
        if execution.status == ExecutionStatus.PASSED:
            return result

        # ---------------------------------------------------------
        # Failure analysis
        # ---------------------------------------------------------

        failure_request = FailureAnalysisRequest(
            repository_path=repository_path,
            file_path=file_path,
            framework=framework.value,
            status=execution.status.value,
            stdout=execution.stdout,
            stderr=execution.stderr,
            error=execution.error,
        )

        failure_analysis = self.failure_analyzer.analyze(
            failure_request
        )

        result["failure_analysis"] = (
            failure_analysis.model_dump()
        )

        if not failure_analysis.repair_required:
            return result

        # ---------------------------------------------------------
        # Read the actual source code if it was not supplied.
        # ---------------------------------------------------------

        if not source_code:
            from pathlib import Path

            repository = Path(repository_path).resolve()
            target = (repository / file_path).resolve()

            try:
                target.relative_to(repository)
            except ValueError as exc:
                raise ValueError(
                    "Test file escapes the repository."
                ) from exc

            if target.exists() and target.is_file():
                source_code = target.read_text(
                    encoding="utf-8"
                )

        # ---------------------------------------------------------
        # Generate repair candidate
        # ---------------------------------------------------------

        healing_request = SelfHealingRequest(
            repository_path=repository_path,
            file_path=file_path,
            failure_type=failure_analysis.failure_type.value,
            root_cause=failure_analysis.root_cause,
            suggested_fix=failure_analysis.suggested_fix,
            source_code=source_code,
        )

        healing_result = self.self_healing.repair(
            healing_request
        )

        result["self_healing"] = (
            healing_result.model_dump()
        )

        # No actual code change means there is nothing safe
        # to apply or re-execute.
        if (
            not healing_result.repaired_code
            or healing_result.repaired_code == source_code
        ):
            result["re_execution"] = {
                "status": "skipped",
                "reason": (
                    "No modified repair candidate was generated."
                ),
            }

            return result

        # ---------------------------------------------------------
        # Validate repaired code
        # ---------------------------------------------------------

        validation = self.code_validator.validate(
            code=healing_result.repaired_code,
            language="python",
        )

        if not validation.valid:
            result["re_execution"] = {
                "status": "repair_rejected",
                "reason": (
                    f"Repair validation failed: "
                    f"{validation.error}"
                ),
            }

            return result

        # ---------------------------------------------------------
        # Backup original file
        # ---------------------------------------------------------

        self.repair_files.create_backup(
            repository_path=repository_path,
            file_path=file_path,
        )

        try:
            # -----------------------------------------------------
            # Apply repair
            # -----------------------------------------------------

            self.repair_files.apply_repair(
                repository_path=repository_path,
                file_path=file_path,
                repaired_code=healing_result.repaired_code,
            )

            # -----------------------------------------------------
            # Re-execute
            # -----------------------------------------------------

            re_execution = await self._execute(
                repository_path=repository_path,
                file_path=file_path,
                framework=framework,
                timeout_seconds=timeout_seconds,
                args=args,
            )

            result["re_execution"] = (
                re_execution.model_dump()
            )

            # -----------------------------------------------------
            # Repair succeeded → keep repaired file
            # -----------------------------------------------------

            if re_execution.status == ExecutionStatus.PASSED:
                self.repair_files.remove_backup(
                    repository_path=repository_path,
                    file_path=file_path,
                )

                result["self_healing"]["status"] = "applied"

                return result

            # -----------------------------------------------------
            # Repair failed → restore original
            # -----------------------------------------------------

            self.repair_files.restore_backup(
                repository_path=repository_path,
                file_path=file_path,
            )

            result["self_healing"]["status"] = "failed"

            return result

        except Exception:
            # Always restore the original file if the repair
            # workflow itself encounters an unexpected error.
            try:
                self.repair_files.restore_backup(
                    repository_path=repository_path,
                    file_path=file_path,
                )
            except Exception:
                pass

            raise