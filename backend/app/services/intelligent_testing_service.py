from app.core.database import AsyncSessionLocal
from app.services.testing_persistence_service import testing_persistence_service

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

from app.analytics.models import AnalyticsRecord
from app.analytics.service import AnalyticsService


class IntelligentTestingService:

    def __init__(self) -> None:
        self.pytest_executor = PytestExecutor()
        self.playwright_executor = PlaywrightExecutor()
        self.selenium_executor = SeleniumExecutor()

        self.failure_analyzer = FailureAnalysisService()
        self.self_healing = SelfHealingService()
        self.repair_files = RepairFileService()
        self.code_validator = GeneratedCodeValidator()

        # Analytics
        self.analytics = AnalyticsService()

    async def _persist_pipeline(
        self,
        execution,
        result: dict,
    ) -> None:
        """
        Persist the complete intelligent testing pipeline result.

        Stores:
        - Test execution
        - Failure analysis
        - Self-healing run
        - Analytics metrics
        """

        async with AsyncSessionLocal() as db:

            # ---------------------------------------------------------
            # Test execution
            # ---------------------------------------------------------

            await testing_persistence_service.save_execution(
                db,
                repository_path=execution.repository_path,
                file_path=execution.file_path,
                framework=execution.framework.value,
                status=execution.status.value,
                exit_code=execution.exit_code,
                stdout=execution.stdout,
                stderr=execution.stderr,
                duration_seconds=execution.duration_seconds,
            )

            # ---------------------------------------------------------
            # Failure analysis
            # ---------------------------------------------------------

            failure_analysis = result.get("failure_analysis")

            if failure_analysis:

                await testing_persistence_service.save_failure_analysis(
                    db,
                    repository_path=execution.repository_path,
                    file_path=execution.file_path,
                    failure_type=failure_analysis["failure_type"],
                    root_cause=failure_analysis["root_cause"],
                    severity=failure_analysis["severity"],
                    suggested_fix=failure_analysis["suggested_fix"],
                    repair_required=failure_analysis["repair_required"],
                )

            # ---------------------------------------------------------
            # Self-healing
            # ---------------------------------------------------------

            self_healing = result.get("self_healing")

            if self_healing:

                await testing_persistence_service.save_self_healing(
                    db,
                    repository_path=execution.repository_path,
                    file_path=execution.file_path,
                    failure_type=(
                        failure_analysis["failure_type"]
                        if failure_analysis
                        else "unknown"
                    ),
                    status=self_healing["status"],
                    explanation=self_healing.get(
                        "explanation",
                        "",
                    ),
                    changes=self_healing.get(
                        "changes",
                        [],
                    ),
                )

            # ---------------------------------------------------------
            # Analytics
            # ---------------------------------------------------------

            analytics = result.get("analytics")

            if analytics:

                metrics = analytics["metrics"]

                await testing_persistence_service.save_analytics(
                    db,
                    repository_path=execution.repository_path,
                    test_generation_validity=metrics[
                        "test_generation_validity"
                    ],
                    coverage_improvement=metrics[
                        "coverage_improvement"
                    ],
                    defect_detection_rate=metrics[
                        "defect_detection_rate"
                    ],
                    development_time_reduction=metrics[
                        "development_time_reduction"
                    ],
                    maintenance_reduction=metrics[
                        "maintenance_reduction"
                    ],
                    self_healing_success_rate=metrics[
                        "self_healing_success_rate"
                    ],
                )

            # ---------------------------------------------------------
            # Commit complete pipeline
            # ---------------------------------------------------------

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

        # =============================================================
        # FIRST EXECUTION
        # =============================================================

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
            "analytics": None,
        }

        # =============================================================
        # FIRST EXECUTION PASSED
        # =============================================================

        if execution.status == ExecutionStatus.PASSED:

            analytics_record = AnalyticsRecord(
                repository_path=repository_path,
                test_generation_valid=True,
                coverage_before=0.0,
                coverage_after=0.0,
                defects_found=0,
                defects_total=0,
                development_time_before_minutes=0.0,
                development_time_after_minutes=0.0,
                maintenance_events_before=0,
                maintenance_events_after=0,
                self_healing_attempts=0,
                self_healing_successes=0,
            )

            analytics_response = self.analytics.calculate(
                analytics_record
            )

            result["analytics"] = (
                analytics_response.model_dump()
            )

            await self._persist_pipeline(
                execution,
                result,
            )

            return result

        # =============================================================
        # FAILURE ANALYSIS
        # =============================================================

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

        # =============================================================
        # FAILURE DOES NOT REQUIRE REPAIR
        # =============================================================

        if not failure_analysis.repair_required:

            analytics_record = AnalyticsRecord(
                repository_path=repository_path,
                test_generation_valid=True,
                defects_found=1,
                defects_total=1,
                self_healing_attempts=0,
                self_healing_successes=0,
            )

            analytics_response = self.analytics.calculate(
                analytics_record
            )

            result["analytics"] = (
                analytics_response.model_dump()
            )

            await self._persist_pipeline(
                execution,
                result,
            )

            return result

        # =============================================================
        # READ ACTUAL SOURCE CODE
        # =============================================================

        if not source_code:

            from pathlib import Path

            repository = Path(
                repository_path
            ).resolve()

            target = (
                repository / file_path
            ).resolve()

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

        # =============================================================
        # GENERATE REPAIR CANDIDATE
        # =============================================================

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

        # =============================================================
        # NO MODIFIED REPAIR CANDIDATE
        # =============================================================

        if (
            not healing_result.repaired_code
            or healing_result.repaired_code == source_code
        ):

            result["re_execution"] = {
                "status": "skipped",
                "reason": (
                    "No modified repair candidate "
                    "was generated."
                ),
            }

            analytics_record = AnalyticsRecord(
                repository_path=repository_path,
                test_generation_valid=True,
                defects_found=1,
                defects_total=1,
                self_healing_attempts=1,
                self_healing_successes=0,
            )

            analytics_response = self.analytics.calculate(
                analytics_record
            )

            result["analytics"] = (
                analytics_response.model_dump()
            )

            await self._persist_pipeline(
                execution,
                result,
            )

            return result

        # =============================================================
        # VALIDATE REPAIRED CODE
        # =============================================================

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

            analytics_record = AnalyticsRecord(
                repository_path=repository_path,
                test_generation_valid=True,
                defects_found=1,
                defects_total=1,
                self_healing_attempts=1,
                self_healing_successes=0,
            )

            analytics_response = self.analytics.calculate(
                analytics_record
            )

            result["analytics"] = (
                analytics_response.model_dump()
            )

            await self._persist_pipeline(
                execution,
                result,
            )

            return result

        # =============================================================
        # BACKUP ORIGINAL FILE
        # =============================================================

        self.repair_files.create_backup(
            repository_path=repository_path,
            file_path=file_path,
        )

        try:

            # =========================================================
            # APPLY REPAIR
            # =========================================================

            self.repair_files.apply_repair(
                repository_path=repository_path,
                file_path=file_path,
                repaired_code=healing_result.repaired_code,
            )

            # =========================================================
            # RE-EXECUTE
            # =========================================================

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

            # =========================================================
            # REPAIR SUCCEEDED
            # =========================================================

            if re_execution.status == ExecutionStatus.PASSED:

                self.repair_files.remove_backup(
                    repository_path=repository_path,
                    file_path=file_path,
                )

                result["self_healing"]["status"] = (
                    "applied"
                )

                analytics_record = AnalyticsRecord(
                    repository_path=repository_path,
                    test_generation_valid=True,
                    defects_found=1,
                    defects_total=1,
                    self_healing_attempts=1,
                    self_healing_successes=1,
                )

                analytics_response = self.analytics.calculate(
                    analytics_record
                )

                result["analytics"] = (
                    analytics_response.model_dump()
                )

                await self._persist_pipeline(
                    execution,
                    result,
                )

                return result

            # =========================================================
            # REPAIR FAILED -> RESTORE ORIGINAL
            # =========================================================

            self.repair_files.restore_backup(
                repository_path=repository_path,
                file_path=file_path,
            )

            result["self_healing"]["status"] = (
                "failed"
            )

            analytics_record = AnalyticsRecord(
                repository_path=repository_path,
                test_generation_valid=True,
                defects_found=1,
                defects_total=1,
                self_healing_attempts=1,
                self_healing_successes=0,
            )

            analytics_response = self.analytics.calculate(
                analytics_record
            )

            result["analytics"] = (
                analytics_response.model_dump()
            )

            await self._persist_pipeline(
                execution,
                result,
            )

            return result

        except Exception:

            # Always restore the original file
            try:

                self.repair_files.restore_backup(
                    repository_path=repository_path,
                    file_path=file_path,
                )

            except Exception:
                pass

            raise