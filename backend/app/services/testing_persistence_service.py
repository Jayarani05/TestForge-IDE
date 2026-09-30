from sqlalchemy.ext.asyncio import AsyncSession

from app.models.testing_persistence import (
    AnalyticsRecordDB,
    FailureAnalysisRecord,
    SelfHealingRecord,
    TestExecutionRecord,
)


class TestingPersistenceService:
    async def save_execution(
        self,
        db: AsyncSession,
        *,
        repository_path: str,
        file_path: str,
        framework: str,
        status: str,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        duration_seconds: float,
    ) -> TestExecutionRecord:
        record = TestExecutionRecord(
            repository_path=repository_path,
            file_path=file_path,
            framework=framework,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration_seconds,
        )
        db.add(record)
        await db.flush()
        return record

    async def save_failure_analysis(
        self,
        db: AsyncSession,
        *,
        repository_path: str,
        file_path: str,
        failure_type: str,
        root_cause: str,
        severity: str,
        suggested_fix: str,
        repair_required: bool,
    ) -> FailureAnalysisRecord:
        record = FailureAnalysisRecord(
            repository_path=repository_path,
            file_path=file_path,
            failure_type=failure_type,
            root_cause=root_cause,
            severity=severity,
            suggested_fix=suggested_fix,
            repair_required=repair_required,
        )
        db.add(record)
        await db.flush()
        return record

    async def save_self_healing(
        self,
        db: AsyncSession,
        *,
        repository_path: str,
        file_path: str,
        failure_type: str,
        status: str,
        explanation: str,
        changes: list[str],
    ) -> SelfHealingRecord:
        record = SelfHealingRecord(
            repository_path=repository_path,
            file_path=file_path,
            failure_type=failure_type,
            status=status,
            explanation=explanation,
            changes="\n".join(changes),
        )
        db.add(record)
        await db.flush()
        return record

    async def save_analytics(
        self,
        db: AsyncSession,
        *,
        repository_path: str,
        test_generation_validity: float,
        coverage_improvement: float,
        defect_detection_rate: float,
        development_time_reduction: float,
        maintenance_reduction: float,
        self_healing_success_rate: float,
    ) -> AnalyticsRecordDB:
        record = AnalyticsRecordDB(
            repository_path=repository_path,
            test_generation_validity=test_generation_validity,
            coverage_improvement=coverage_improvement,
            defect_detection_rate=defect_detection_rate,
            development_time_reduction=development_time_reduction,
            maintenance_reduction=maintenance_reduction,
            self_healing_success_rate=self_healing_success_rate,
        )
        db.add(record)
        await db.flush()
        return record

    async def commit(self, db: AsyncSession) -> None:
        await db.commit()


testing_persistence_service = TestingPersistenceService()
