import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.failure_analysis import FailureAnalysisResult
from app.agents.self_healing import SelfHealingResult
from app.execution.models import ExecutionResult
from app.models.testing_persistence import (
    AnalyticsRecordDB,
    FailureAnalysisRecord,
    SelfHealingRecord,
    TestExecutionRecord,
)


class TestingPersistenceService:
    async def get_execution(
        self,
        db: AsyncSession,
        execution_id: str,
    ) -> TestExecutionRecord | None:
        result = await db.execute(
            select(TestExecutionRecord).where(
                TestExecutionRecord.execution_id == execution_id
            )
        )
        return result.scalar_one_or_none()

    async def save_execution(
        self,
        db: AsyncSession,
        execution: ExecutionResult,
    ) -> TestExecutionRecord:
        existing = await self.get_execution(db, execution.execution_id)
        if existing is not None:
            if self._execution_matches(existing, execution):
                return existing
            raise ValueError("Execution identifier conflicts with a stored result.")

        record = TestExecutionRecord(
            execution_id=execution.execution_id,
            repository_path=execution.repository_path,
            file_path=execution.file_path,
            framework=execution.framework.value,
            status=execution.status.value,
            exit_code=execution.exit_code,
            stdout=execution.stdout,
            stderr=execution.stderr,
            duration_seconds=execution.duration_seconds,
            error=execution.error,
            coverage_percent=execution.coverage_percent,
            coverage_covered_statements=execution.coverage_covered_statements,
            coverage_total_statements=execution.coverage_total_statements,
            coverage_error=execution.coverage_error,
            source_digest=execution.source_digest,
        )
        db.add(record)
        await db.flush()
        return record

    async def get_failure_analysis(
        self,
        db: AsyncSession,
        execution_id: str,
    ) -> FailureAnalysisRecord | None:
        result = await db.execute(
            select(FailureAnalysisRecord).where(
                FailureAnalysisRecord.execution_id == execution_id
            )
        )
        return result.scalar_one_or_none()

    async def save_failure_analysis(
        self,
        db: AsyncSession,
        execution: ExecutionResult,
        analysis: FailureAnalysisResult,
    ) -> FailureAnalysisRecord:
        stored_execution = await self.get_execution(db, execution.execution_id)
        if stored_execution is None or not self._execution_matches(
            stored_execution,
            execution,
        ):
            raise ValueError("Failure analysis requires its persisted execution.")
        if (
            analysis.execution_id != execution.execution_id
            or analysis.execution_file != execution.file_path
            or analysis.execution_status != execution.status
        ):
            raise ValueError("Failure analysis does not match the stored execution.")

        existing = await self.get_failure_analysis(db, execution.execution_id)
        values = self._analysis_values(execution, analysis)
        if existing is not None:
            if self._analysis_matches(existing, values):
                return existing
            raise ValueError(
                "A different failure analysis is already stored for this execution."
            )

        record = FailureAnalysisRecord(**values)
        db.add(record)
        await db.flush()
        return record

    async def get_repair(
        self,
        db: AsyncSession,
        repair_id: str,
    ) -> SelfHealingRecord | None:
        result = await db.execute(
            select(SelfHealingRecord).where(
                SelfHealingRecord.repair_id == repair_id
            )
        )
        return result.scalar_one_or_none()

    async def save_repair_candidate(
        self,
        db: AsyncSession,
        execution: ExecutionResult,
        analysis: FailureAnalysisResult,
        candidate: SelfHealingResult,
    ) -> SelfHealingRecord:
        stored_execution = await self.get_execution(db, execution.execution_id)
        stored_analysis = await self.get_failure_analysis(
            db,
            execution.execution_id,
        )
        if (
            stored_execution is None
            or not self._execution_matches(stored_execution, execution)
            or stored_analysis is None
            or not self._analysis_matches(
                stored_analysis,
                self._analysis_values(execution, analysis),
            )
            or candidate.file_path != execution.file_path
            or not candidate.eligible_for_review
            or candidate.original_code == candidate.repaired_code
        ):
            raise ValueError(
                "Repair candidate references do not match persisted execution history."
            )
        if analysis.execution_id != execution.execution_id:
            raise ValueError("Repair analysis does not match its execution.")
        existing = await self.get_repair(db, candidate.repair_id)
        if existing is not None:
            raise ValueError("Repair identifier already exists.")

        record = SelfHealingRecord(
            repair_id=candidate.repair_id,
            execution_id=execution.execution_id,
            failure_analysis_id=stored_analysis.id,
            repository_path=execution.repository_path,
            file_path=candidate.file_path,
            failure_type=analysis.failure_type.value,
            status="generated",
            explanation=candidate.explanation,
            changes="\n".join(candidate.changes),
            original_code=candidate.original_code,
            proposed_code=candidate.repaired_code,
            review_status="pending_review",
        )
        db.add(record)
        await db.flush()
        return record

    async def record_repair_applied(
        self,
        db: AsyncSession,
        repair_id: str,
        *,
        approved: bool,
        outcome: str,
    ) -> SelfHealingRecord:
        if not approved:
            raise ValueError("Explicit approval is required to record an applied repair.")
        record = await self.get_repair(db, repair_id)
        if record is None or record.review_status != "pending_review":
            raise ValueError("Only a reviewed repair candidate can be applied.")
        record.status = "applied"
        record.review_status = "applied"
        record.apply_approved = True
        record.apply_outcome = outcome
        record.applied_at = datetime.utcnow()
        await db.flush()
        return record

    async def record_repair_restored(
        self,
        db: AsyncSession,
        repair_id: str,
        *,
        approved: bool,
        outcome: str,
    ) -> SelfHealingRecord:
        if not approved:
            raise ValueError("Explicit approval is required to record restoration.")
        record = await self.get_repair(db, repair_id)
        if record is None:
            raise ValueError("Repair candidate was not found.")
        if record.review_status != "applied":
            raise ValueError("Only an applied repair can be restored.")
        record.status = "restored"
        record.review_status = "restored"
        record.restore_outcome = outcome
        record.restored_at = datetime.utcnow()
        await db.flush()
        return record

    async def save_failure_analysis_legacy(
        self,
        db: AsyncSession,
        *,
        repository_path: str,
        file_path: str,
        failure_type: str,
        root_cause: str | None,
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
        coverage_improvement: float | None,
        defect_detection_rate: float,
        development_time_reduction: float,
        maintenance_reduction: float,
        self_healing_success_rate: float,
        coverage_before: float | None = None,
        coverage_after: float | None = None,
    ) -> AnalyticsRecordDB:
        record = AnalyticsRecordDB(
            repository_path=repository_path,
            test_generation_validity=test_generation_validity,
            coverage_before=coverage_before,
            coverage_after=coverage_after,
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

    @staticmethod
    def _execution_matches(
        record: TestExecutionRecord,
        execution: ExecutionResult,
    ) -> bool:
        return all(
            (
                record.repository_path == execution.repository_path,
                record.file_path == execution.file_path,
                record.framework == execution.framework.value,
                record.status == execution.status.value,
                record.exit_code == execution.exit_code,
                record.stdout == execution.stdout,
                record.stderr == execution.stderr,
                record.duration_seconds == execution.duration_seconds,
                record.error == execution.error,
                record.coverage_percent == execution.coverage_percent,
                record.coverage_covered_statements
                == execution.coverage_covered_statements,
                record.coverage_total_statements == execution.coverage_total_statements,
                record.coverage_error == execution.coverage_error,
                record.source_digest == execution.source_digest,
            )
        )

    @staticmethod
    def _analysis_values(
        execution: ExecutionResult,
        analysis: FailureAnalysisResult,
    ) -> dict[str, object]:
        return {
            "execution_id": execution.execution_id,
            "repository_path": execution.repository_path,
            "file_path": execution.file_path,
            "failure_type": analysis.failure_type.value,
            "root_cause": analysis.root_cause,
            "observed_details": json.dumps(analysis.observed_details),
            "evidence": json.dumps(analysis.evidence),
            "inferred_explanation": analysis.inferred_explanation,
            "recommendations": json.dumps(analysis.recommendations),
            "severity": analysis.severity,
            "suggested_fix": "\n".join(analysis.recommendations),
            "repair_required": analysis.repair_required,
        }

    @staticmethod
    def _analysis_matches(
        record: FailureAnalysisRecord,
        values: dict[str, object],
    ) -> bool:
        return all(
            getattr(record, field) == value
            for field, value in values.items()
        )


testing_persistence_service = TestingPersistenceService()
