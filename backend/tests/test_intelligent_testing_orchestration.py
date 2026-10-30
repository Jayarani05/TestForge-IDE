import asyncio

from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
    ExecutionStatus,
)
from app.services.intelligent_testing_service import IntelligentTestingService


def _execution(tmp_path, status):
    return ExecutionResult(
        repository_path=str(tmp_path),
        file_path="tests/test_sample.py",
        framework=ExecutionFramework.PYTEST,
        status=status,
        exit_code=0 if status == ExecutionStatus.PASSED else 1,
        stdout="1 passed" if status == ExecutionStatus.PASSED else "",
        stderr="" if status == ExecutionStatus.PASSED else "AssertionError",
        duration_seconds=0.1,
    )


def test_pipeline_reports_failure_for_review_without_applying_or_rerunning(
    tmp_path,
    monkeypatch,
):
    service = IntelligentTestingService()
    execution = _execution(tmp_path, ExecutionStatus.FAILED)
    execution_calls = []
    persisted = []

    async def execute(**kwargs):
        execution_calls.append(kwargs)
        return execution

    async def persist(result, analysis):
        persisted.append((result, analysis))

    monkeypatch.setattr(service, "_execute", execute)
    monkeypatch.setattr(service, "_persist_pipeline", persist)

    result = asyncio.run(
        service.execute_and_analyze(
            repository_path=str(tmp_path),
            file_path=execution.file_path,
            framework=ExecutionFramework.PYTEST,
        )
    )

    assert len(execution_calls) == 1
    assert result["execution"]["execution_id"] == execution.execution_id
    assert result["failure_analysis"]["execution_id"] == execution.execution_id
    assert result["failure_analysis"]["repair_required"] is True
    assert result["self_healing"] is None
    assert result["re_execution"] is None
    assert len(persisted) == 1


def test_pipeline_does_not_run_failure_analysis_after_success(tmp_path, monkeypatch):
    service = IntelligentTestingService()
    execution = _execution(tmp_path, ExecutionStatus.PASSED)
    persisted = []

    async def execute(**kwargs):
        return execution

    async def persist(result, analysis):
        persisted.append((result, analysis))

    monkeypatch.setattr(service, "_execute", execute)
    monkeypatch.setattr(service, "_persist_pipeline", persist)
    monkeypatch.setattr(
        service.failure_analyzer,
        "analyze",
        lambda request: (_ for _ in ()).throw(AssertionError("unexpected analysis")),
    )

    result = asyncio.run(
        service.execute_and_analyze(
            repository_path=str(tmp_path),
            file_path=execution.file_path,
            framework=ExecutionFramework.PYTEST,
        )
    )

    assert result["execution"]["status"] == ExecutionStatus.PASSED.value
    assert result["failure_analysis"] is None
    assert result["self_healing"] is None
    assert result["re_execution"] is None
    assert persisted == [(execution, None)]
