import asyncio
from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.agents.failure_analysis import (
    FailureAnalysisResult,
    FailureType,
)
from app.agents.self_healing import (
    RepairStatus,
    SelfHealingResult,
)
from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
    ExecutionStatus,
)
from app.models.testing_persistence import (
    AnalyticsRecordDB,
    FailureAnalysisRecord,
    SelfHealingRecord,
    TestExecutionRecord as _TestExecutionRecord,
)
from app.services.history_schemas import (
    AnalyticsHistoryItem,
    ExecutionHistoryItem,
    FailureHistoryItem,
    SelfHealingHistoryItem,
)
from app.services.history_service import testing_history_service
from app.services.testing_persistence_service import TestingPersistenceService


class SQLiteAsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    def add(self, record):
        self.session.add(record)

    async def execute(self, statement):
        return self.session.execute(statement)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()


class FakeResult:
    def __init__(self, records):
        self.records = records

    def scalar_one_or_none(self):
        return self.records[0] if self.records else None

    def scalars(self):
        return self

    def all(self):
        return self.records


class FakeAsyncSession:
    def __init__(self, *, fail_commit=False):
        self.records = {}
        self.pending = []
        self.next_id = 1
        self.fail_commit = fail_commit

    def add(self, record):
        self.pending.append(record)

    async def execute(self, statement):
        model = statement.column_descriptions[0]["entity"]
        records = [*self.records.get(model, []), *self.pending]
        where = statement.whereclause
        if where is not None:
            attribute = where.left.key
            expected = where.right.value
            records = [
                record for record in records
                if isinstance(record, model)
                and getattr(record, attribute) == expected
            ]
        else:
            records = [record for record in records if isinstance(record, model)]
        return FakeResult(records)

    async def flush(self):
        pending, self.pending = self.pending, []
        for record in pending:
            if getattr(record, "id", None) is None:
                record.id = self.next_id
                self.next_id += 1
            if getattr(record, "created_at", None) is None:
                record.created_at = datetime.utcnow()
            self.records.setdefault(type(record), []).append(record)

    async def commit(self):
        if self.fail_commit:
            raise RuntimeError("simulated database commit failure")


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture
def sqlite_history_engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _TestExecutionRecord.__table__.create(engine)
    FailureAnalysisRecord.__table__.create(engine)
    SelfHealingRecord.__table__.create(engine)
    AnalyticsRecordDB.__table__.create(engine)
    yield engine
    engine.dispose()


def execution_result(**overrides):
    values = {
        "execution_id": "execution-1",
        "repository_path": "C:/workspace",
        "file_path": "tests/test_sample.py",
        "framework": ExecutionFramework.PYTEST,
        "status": ExecutionStatus.FAILED,
        "exit_code": 1,
        "stdout": "AssertionError",
        "stderr": "",
        "duration_seconds": 0.5,
    }
    values.update(overrides)
    return ExecutionResult(**values)


def failure_analysis(execution):
    return FailureAnalysisResult(
        execution_id=execution.execution_id,
        execution_file=execution.file_path,
        execution_status=execution.status,
        failure_type=FailureType.ASSERTION_FAILURE,
        observed_details=["Assertion failure observed."],
        evidence=["assert actual == expected"],
        root_cause=None,
        inferred_explanation=None,
        recommendations=["Review the recorded expected and actual values."],
        severity="medium",
        repair_required=True,
    )


def repair_candidate(file_path="tests/test_sample.py"):
    return SelfHealingResult(
        repair_id="repair-1",
        status=RepairStatus.GENERATED,
        file_path=file_path,
        original_code="assert actual == expected",
        repaired_code="assert actual == actual",
        explanation="Candidate based on the recorded assertion evidence.",
        changes=["Update assertion."],
        evidence=["assert actual == expected"],
        eligible_for_review=True,
    )


def test_execution_history_persists_and_retrieves_actual_result_fields():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    execution = execution_result(
        status=ExecutionStatus.PASSED,
        exit_code=0,
        coverage_percent=50,
        coverage_covered_statements=1,
        coverage_total_statements=2,
        source_digest="a" * 64,
    )

    stored = run(service.save_execution(db, execution))
    duplicate = run(service.save_execution(db, execution))
    retrieved = run(service.get_execution(db, execution.execution_id))
    history = ExecutionHistoryItem.model_validate(stored, from_attributes=True)

    assert duplicate is stored
    assert retrieved is stored
    assert history.execution_id == execution.execution_id
    assert history.coverage_percent == 50
    assert history.coverage_total_statements == 2
    assert history.source_digest == "a" * 64


def test_execution_failure_and_repair_history_survive_database_sessions(
    sqlite_history_engine,
):
    service = TestingPersistenceService()
    execution = execution_result()
    analysis = failure_analysis(execution)
    candidate = repair_candidate()

    with Session(sqlite_history_engine, expire_on_commit=False) as session:
        db = SQLiteAsyncSessionAdapter(session)
        run(service.save_execution(db, execution))
        run(service.commit(db))

    with Session(sqlite_history_engine, expire_on_commit=False) as session:
        db = SQLiteAsyncSessionAdapter(session)
        stored_execution = run(service.get_execution(db, execution.execution_id))
        assert stored_execution is not None
        assert stored_execution.stdout == execution.stdout
        assert stored_execution.execution_id == execution.execution_id

        stored_analysis = run(
            service.save_failure_analysis(db, execution, analysis)
        )
        run(service.commit(db))

    with Session(sqlite_history_engine, expire_on_commit=False) as session:
        db = SQLiteAsyncSessionAdapter(session)
        retrieved_analysis = run(
            service.get_failure_analysis(db, execution.execution_id)
        )
        assert retrieved_analysis is not None
        assert retrieved_analysis.id == stored_analysis.id
        assert retrieved_analysis.evidence == '["assert actual == expected"]'

        stored_candidate = run(
            service.save_repair_candidate(db, execution, analysis, candidate)
        )
        run(service.commit(db))
        assert stored_candidate.failure_analysis_id == stored_analysis.id

        run(
            service.record_repair_applied(
                db,
                candidate.repair_id,
                approved=True,
                outcome="Applied after explicit approval.",
            )
        )
        run(service.commit(db))
        run(
            service.record_repair_restored(
                db,
                candidate.repair_id,
                approved=True,
                outcome="Restored after explicit approval.",
            )
        )
        run(service.commit(db))

    with Session(sqlite_history_engine, expire_on_commit=False) as session:
        db = SQLiteAsyncSessionAdapter(session)
        retrieved_candidate = run(service.get_repair(db, candidate.repair_id))
        assert retrieved_candidate is not None
        assert retrieved_candidate.execution_id == execution.execution_id
        assert retrieved_candidate.review_status == "restored"
        assert retrieved_candidate.apply_approved is True
        assert retrieved_candidate.restore_outcome == "Restored after explicit approval."


def test_execution_history_rejects_conflicting_duplicate_ids():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    run(service.save_execution(db, execution_result()))

    with pytest.raises(ValueError, match="conflicts"):
        run(service.save_execution(
            db,
            execution_result(stdout="Different result"),
        ))


def test_failure_history_is_associated_and_preserves_observed_evidence():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    execution = execution_result()
    run(service.save_execution(db, execution))

    stored = run(service.save_failure_analysis(
        db,
        execution,
        failure_analysis(execution),
    ))
    duplicate = run(service.save_failure_analysis(
        db,
        execution,
        failure_analysis(execution),
    ))
    retrieved = run(service.get_failure_analysis(db, execution.execution_id))
    history = FailureHistoryItem.model_validate(stored, from_attributes=True)

    assert duplicate is stored
    assert retrieved is stored
    assert history.execution_id == execution.execution_id
    assert history.evidence == ["assert actual == expected"]
    assert history.root_cause is None


def test_failure_history_rejects_missing_or_mismatched_execution():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    execution = execution_result()

    with pytest.raises(ValueError, match="persisted execution"):
        run(service.save_failure_analysis(
            db,
            execution,
            failure_analysis(execution),
        ))


def test_failure_history_rejects_conflicting_duplicate_analysis():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    execution = execution_result()
    run(service.save_execution(db, execution))
    analysis = failure_analysis(execution)
    run(service.save_failure_analysis(db, execution, analysis))

    with pytest.raises(ValueError, match="different failure analysis"):
        run(
            service.save_failure_analysis(
                db,
                execution,
                analysis.model_copy(update={"evidence": ["different evidence"]}),
            )
        )

    run(service.save_execution(db, execution))
    with pytest.raises(ValueError, match="does not match"):
        run(service.save_failure_analysis(
            db,
            execution,
            failure_analysis(execution).model_copy(
                update={"execution_file": "tests/other.py"}
            ),
        ))


def test_repair_history_enforces_associations_and_records_approved_lifecycle():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    execution = execution_result()
    analysis = failure_analysis(execution)
    run(service.save_execution(db, execution))
    stored_analysis = run(service.save_failure_analysis(db, execution, analysis))

    with pytest.raises(ValueError, match="references"):
        run(service.save_repair_candidate(
            db,
            execution,
            analysis,
            repair_candidate("tests/other.py"),
        ))
    with pytest.raises(ValueError, match="references"):
        run(
            service.save_repair_candidate(
                db,
                execution,
                analysis.model_copy(update={"evidence": ["unrelated evidence"]}),
                repair_candidate(),
            )
        )

    candidate = repair_candidate()
    stored = run(service.save_repair_candidate(
        db,
        execution,
        analysis,
        candidate,
    ))
    history = SelfHealingHistoryItem.model_validate(stored, from_attributes=True)
    assert stored.failure_analysis_id == stored_analysis.id
    assert stored.execution_id == execution.execution_id
    assert history.original_code == candidate.original_code
    assert history.proposed_code == candidate.repaired_code
    with pytest.raises(ValueError, match="already exists"):
        run(service.save_repair_candidate(db, execution, analysis, candidate))

    with pytest.raises(ValueError, match="Explicit approval"):
        run(service.record_repair_applied(
            db,
            candidate.repair_id,
            approved=False,
            outcome="not applied",
        ))

    applied = run(service.record_repair_applied(
        db,
        candidate.repair_id,
        approved=True,
        outcome="Applied after explicit approval.",
    ))
    restored = run(service.record_repair_restored(
        db,
        candidate.repair_id,
        approved=True,
        outcome="Restored after explicit approval.",
    ))

    assert applied.apply_approved is True
    assert applied.apply_outcome == "Applied after explicit approval."
    assert restored.status == "restored"
    assert restored.restore_outcome == "Restored after explicit approval."
    assert run(service.get_repair(db, candidate.repair_id)) is stored


def test_repair_history_rejects_missing_analysis_and_invalid_lifecycle():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    execution = execution_result()
    analysis = failure_analysis(execution)
    run(service.save_execution(db, execution))

    with pytest.raises(ValueError, match="references"):
        run(service.save_repair_candidate(
            db,
            execution,
            analysis,
            repair_candidate(),
        ))
    with pytest.raises(ValueError, match="not found"):
        run(service.record_repair_restored(
            db,
            "missing-repair",
            approved=True,
            outcome="restore",
        ))


def test_persistence_commit_failure_is_not_silently_reported():
    db = FakeAsyncSession(fail_commit=True)
    service = TestingPersistenceService()

    run(service.save_execution(db, execution_result()))
    with pytest.raises(RuntimeError, match="commit failure"):
        run(service.commit(db))


def test_history_schemas_reject_impossible_coverage_and_malformed_evidence():
    with pytest.raises(ValidationError, match="percentage does not match"):
        ExecutionHistoryItem(
            id=1,
            execution_id="execution-1",
            repository_path="repo",
            file_path="tests/test_sample.py",
            framework="pytest",
            status="passed",
            exit_code=0,
            stdout="",
            stderr="",
            duration_seconds=0.1,
            coverage_percent=50,
            coverage_covered_statements=1,
            coverage_total_statements=3,
            created_at=datetime.utcnow(),
        )

    with pytest.raises(ValidationError, match="malformed"):
        FailureHistoryItem(
            id=1,
            repository_path="repo",
            file_path="tests/test_sample.py",
            failure_type="unknown",
            root_cause=None,
            observed_details="not-json",
            evidence=[],
            recommendations=[],
            severity="medium",
            suggested_fix="",
            repair_required=False,
            created_at=datetime.utcnow(),
        )

    with pytest.raises(ValidationError):
        AnalyticsHistoryItem(
            id=1,
            repository_path="repo",
            test_generation_validity=0,
            coverage_before=None,
            coverage_after=None,
            coverage_improvement=float("nan"),
            defect_detection_rate=0,
            development_time_reduction=0,
            maintenance_reduction=0,
            self_healing_success_rate=0,
        )

def test_analytics_history_persists_and_retrieves_actual_metric_values():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    stored = run(service.save_analytics(
        db,
        repository_path="repo",
        test_generation_validity=100,
        coverage_before=40,
        coverage_after=62.5,
        coverage_improvement=22.5,
        defect_detection_rate=75,
        development_time_reduction=25,
        maintenance_reduction=30,
        self_healing_success_rate=60,
    ))
    duplicate = run(service.save_analytics(
        db,
        repository_path="repo",
        test_generation_validity=100,
        coverage_before=40,
        coverage_after=62.5,
        coverage_improvement=22.5,
        defect_detection_rate=75,
        development_time_reduction=25,
        maintenance_reduction=30,
        self_healing_success_rate=60,
    ))
    retrieved = run(service.get_analytics(db, stored.id))
    history = AnalyticsHistoryItem.model_validate(stored, from_attributes=True)

    assert duplicate is stored
    assert retrieved is stored
    assert history.test_generation_validity == 100
    assert history.coverage_improvement == 22.5
    assert history.coverage_before == 40
    assert history.coverage_after == 62.5
    assert history.created_at is not None


def test_analytics_history_handles_missing_measurements():
    db = FakeAsyncSession()
    service = TestingPersistenceService()
    stored = run(service.save_analytics(
        db,
        repository_path="repo",
        test_generation_validity=0,
        coverage_improvement=None,
        defect_detection_rate=0,
        development_time_reduction=0,
        maintenance_reduction=0,
        self_healing_success_rate=0,
    ))
    history = AnalyticsHistoryItem.model_validate(stored, from_attributes=True)

    assert history.coverage_before is None
    assert history.coverage_after is None
    assert history.coverage_improvement is None


def test_analytics_history_rejects_invalid_values_and_duplicates_distinctly():
    db = FakeAsyncSession()
    service = TestingPersistenceService()

    with pytest.raises(ValueError, match="between 0 and 100"):
        run(service.save_analytics(
            db,
            repository_path="repo",
            test_generation_validity=101,
            coverage_improvement=None,
            defect_detection_rate=0,
            development_time_reduction=0,
            maintenance_reduction=0,
            self_healing_success_rate=0,
        ))

    with pytest.raises(ValueError, match="does not match"):
        run(service.save_analytics(
            db,
            repository_path="repo",
            test_generation_validity=0,
            coverage_before=40,
            coverage_after=62.5,
            coverage_improvement=10,
            defect_detection_rate=0,
            development_time_reduction=0,
            maintenance_reduction=0,
            self_healing_success_rate=0,
        ))

    with pytest.raises(ValueError, match="required"):
        run(service.save_analytics(
            db,
            repository_path="",
            test_generation_validity=0,
            coverage_improvement=None,
            defect_detection_rate=0,
            development_time_reduction=0,
            maintenance_reduction=0,
            self_healing_success_rate=0,
        ))


def test_analytics_history_survives_database_sessions(sqlite_history_engine):
    service = TestingPersistenceService()

    with Session(sqlite_history_engine, expire_on_commit=False) as session:
        db = SQLiteAsyncSessionAdapter(session)
        stored = run(service.save_analytics(
            db,
            repository_path="repo",
            test_generation_validity=50,
            coverage_before=40,
            coverage_after=40,
            coverage_improvement=0,
            defect_detection_rate=0,
            development_time_reduction=0,
            maintenance_reduction=0,
            self_healing_success_rate=0,
        ))
        run(service.commit(db))

    with Session(sqlite_history_engine, expire_on_commit=False) as session:
        db = SQLiteAsyncSessionAdapter(session)
        history_service_records = run(testing_history_service.analytics(db, "repo", 10))
        assert len(history_service_records) == 1
        assert history_service_records[0].coverage_improvement == 0
