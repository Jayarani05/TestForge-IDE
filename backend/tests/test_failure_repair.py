import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.database import get_db
from app.agents.failure_analysis import (
    FailureAnalysisRequest,
    FailureType,
    analyze_failure,
)
from app.agents.providers import LLMResponse
from app.agents.self_healing import (
    RepairStatus,
    SelfHealingRequest,
    SelfHealingResult,
)
from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
    ExecutionStatus,
)
from app.execution.process_manager import ProcessManager
from app.execution.result_registry import execution_result_registry
from app.main import app
from app.services.repair_file_service import RepairFileService
from app.services.self_healing_service import SelfHealingService


def _execution(
    *,
    status: ExecutionStatus = ExecutionStatus.FAILED,
    stdout: str = "",
    stderr: str = "",
    error: str | None = None,
    exit_code: int | None = 1,
) -> ExecutionResult:
    return ExecutionResult(
        repository_path="repo",
        file_path="tests/test_sample.py",
        framework=ExecutionFramework.PYTEST,
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.8,
        error=error,
    )


def _analysis_request(execution: ExecutionResult) -> FailureAnalysisRequest:
    return FailureAnalysisRequest(execution=execution)


def test_failure_analysis_reports_assertion_facts_without_inventing_root_cause():
    result = analyze_failure(
        _analysis_request(
            _execution(stderr="AssertionError: expected 4, got 3")
        )
    )

    assert result.failure_type == FailureType.ASSERTION_FAILURE
    assert result.root_cause is None
    assert result.inferred_explanation is None
    assert result.observed_details
    assert "AssertionError: expected 4, got 3" in result.evidence
    assert result.execution_status == ExecutionStatus.FAILED


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("SyntaxError: invalid syntax", FailureType.SYNTAX_ERROR),
        ("ModuleNotFoundError: No module named 'sample'", FailureType.IMPORT_ERROR),
    ],
)
def test_failure_analysis_classifies_syntax_and_import_errors(output, expected):
    result = analyze_failure(_analysis_request(_execution(stderr=output)))

    assert result.failure_type == expected
    assert result.root_cause is None
    assert result.evidence


def test_failure_analysis_distinguishes_runner_errors_and_timeouts():
    runner = analyze_failure(
        _analysis_request(
            _execution(
                status=ExecutionStatus.ERROR,
                error="Test runner executable is unavailable.",
                exit_code=None,
            )
        )
    )
    timeout = analyze_failure(
        _analysis_request(
            _execution(
                status=ExecutionStatus.TIMEOUT,
                error="Process timed out after 2 seconds.",
                exit_code=-9,
            )
        )
    )

    assert runner.failure_type == FailureType.RUNNER_ERROR
    assert "runner error" in runner.observed_details[0].lower()
    assert timeout.failure_type == FailureType.TIMEOUT
    assert timeout.root_cause is None
    assert timeout.execution_status == ExecutionStatus.TIMEOUT


def test_failure_analysis_handles_empty_output_and_rejects_success():
    result = analyze_failure(
        _analysis_request(_execution(stderr="", stdout=""))
    )
    assert result.failure_type == FailureType.UNKNOWN
    assert result.root_cause is None
    assert result.evidence == []
    assert result.repair_required is False

    with pytest.raises(ValidationError):
        FailureAnalysisRequest(
            execution=_execution(status=ExecutionStatus.PASSED, exit_code=0)
        )
    with pytest.raises(ValidationError):
        FailureAnalysisRequest.model_validate(
            {"execution": {"execution_id": "broken", "status": "failed"}}
        )


def test_failure_analysis_redacts_secrets_from_evidence():
    result = analyze_failure(
        _analysis_request(
            _execution(
                stderr="Authorization: Bearer abc.secret-value "
                "password=private-value AssertionError"
            )
        )
    )

    assert result.failure_type == FailureType.ASSERTION_FAILURE
    assert "abc.secret-value" not in repr(result)
    assert "private-value" not in repr(result)
    assert "[REDACTED]" in repr(result)


def test_process_output_redaction_covers_bearer_and_named_credentials():
    output = ProcessManager._redact_secrets(
        "Authorization: Bearer abc.def token=private-token "
        "api_key='private-key'",
        {},
    )

    assert "abc.def" not in output
    assert "private-token" not in output
    assert "private-key" not in output
    assert output.count("[REDACTED]") == 3


def test_failure_analysis_api_requires_the_exact_recorded_execution(monkeypatch):
    async def override_db():
        yield object()

    async def persist_analysis(*_args, **_kwargs):
        return None

    async def persist_commit(*_args, **_kwargs):
        return None

    from app.api.v1 import failure_analysis as failure_analysis_api

    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    monkeypatch.setattr(
        failure_analysis_api.testing_persistence_service,
        "save_failure_analysis",
        persist_analysis,
    )
    monkeypatch.setattr(
        failure_analysis_api.testing_persistence_service,
        "commit",
        persist_commit,
    )
    execution = _execution(stderr="AssertionError: expected 4, got 3")
    execution_result_registry.store(execution)
    with TestClient(app) as client:
        valid = client.post(
            "/failure-analysis/analyze",
            json={"execution": execution.model_dump(mode="json")},
        )
        altered = execution.model_copy(
            update={"stderr": "different output"}
        )
        invalid = client.post(
            "/failure-analysis/analyze",
            json={"execution": altered.model_dump(mode="json")},
        )

    assert valid.status_code == 200
    assert valid.json()["execution_id"] == execution.execution_id
    assert invalid.status_code == 409


def test_repair_api_requires_recorded_execution_and_explicit_approval(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace

    from app.api.v1 import self_healing as repair_api
    from app.api.v1.failure_analysis import service as analysis_service

    async def override_db():
        yield object()

    async def persist_candidate(*_args, **_kwargs):
        return None

    async def persist_commit(*_args, **_kwargs):
        return None

    async def get_candidate(_db, repair_id):
        if repair_id == "route-candidate":
            return SimpleNamespace(review_status="pending_review")
        return None

    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    monkeypatch.setattr(
        repair_api.testing_persistence_service,
        "save_repair_candidate",
        persist_candidate,
    )
    monkeypatch.setattr(
        repair_api.testing_persistence_service,
        "commit",
        persist_commit,
    )
    monkeypatch.setattr(
        repair_api.testing_persistence_service,
        "get_repair",
        get_candidate,
    )

    target = tmp_path / "tests" / "test_sample.py"
    target.parent.mkdir()
    target.write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    request = _repair_request(tmp_path)
    recorded_analysis = analysis_service.analyze(
        FailureAnalysisRequest(execution=request.execution)
    )
    request = request.model_copy(update={"analysis": recorded_analysis})
    execution_result_registry.store(request.execution)
    candidate = SelfHealingResult(
        repair_id="route-candidate",
        file_path=request.execution.file_path,
        original_code="before",
        repaired_code="after",
        explanation="Mocked candidate response.",
        changes=["Mock change."],
        evidence=["Mock evidence."],
    )

    async def generate(request):
        assert request.execution.execution_id == request.analysis.execution_id
        return candidate

    monkeypatch.setattr(repair_api.service, "repair", generate)
    with TestClient(app) as client:
        valid = client.post(
            "/self-healing/repair",
            json=request.model_dump(mode="json"),
        )
        stale_execution = request.execution.model_copy(
            update={"stderr": "altered result"}
        )
        stale = client.post(
            "/self-healing/repair",
            json=request.model_copy(
                update={"execution": stale_execution}
            ).model_dump(mode="json"),
        )
        denied_apply = client.post(
            "/self-healing/apply",
            json={"repair_id": "route-candidate", "approved": False},
        )
        denied_restore = client.post(
            "/self-healing/restore",
            json={"repair_id": "route-candidate", "approved": False},
        )

    assert valid.status_code == 200
    assert valid.json()["repair_id"] == "route-candidate"
    assert stale.status_code == 409
    assert denied_apply.status_code == 409
    assert "approval" in denied_apply.json()["detail"].lower()
    assert denied_restore.status_code == 400


class FakeOrchestrator:
    def __init__(self, content: str | Exception) -> None:
        self.content = content
        self.request = None
        self.provider_name = ""

    async def generate(self, request, provider_name="auto"):
        self.request = request
        self.provider_name = provider_name
        if isinstance(self.content, Exception):
            raise self.content
        return LLMResponse(
            provider="mock",
            model="unit-test",
            content=self.content,
        )


def _candidate_payload(code: str, **overrides) -> str:
    candidate = {
        "repaired_code": code,
        "explanation": "Correct the demonstrated expected value.",
        "changes": ["Updated the mismatched expected value."],
        "target_line_start": 2,
        "target_line_end": 2,
    }
    candidate.update(overrides)
    return json.dumps(candidate)


def _repair_request(repository, file_path="tests/test_sample.py"):
    execution = _execution(
        stdout="FAILED tests/test_sample.py::test_sample",
        stderr="AssertionError: expected 4, got 3",
    ).model_copy(update={"repository_path": str(repository), "file_path": file_path})
    analysis = analyze_failure(_analysis_request(execution))
    return SelfHealingRequest(
        repository_path=str(repository),
        execution=execution,
        analysis=analysis,
    )


def test_repair_candidate_uses_actual_source_and_is_only_registered_for_review(tmp_path):
    target = tmp_path / "tests" / "test_sample.py"
    target.parent.mkdir()
    original = "def test_sample():\n    assert 3 == 4\n"
    proposed = "def test_sample():\n    assert 3 == 3\n"
    target.write_text(original, encoding="utf-8")
    stored_original = target.read_bytes().decode("utf-8")
    orchestrator = FakeOrchestrator(_candidate_payload(proposed))
    service = SelfHealingService(orchestrator=orchestrator)

    candidate = asyncio.run(service.repair(_repair_request(tmp_path)))

    assert candidate.status == RepairStatus.GENERATED
    assert candidate.eligible_for_review is True
    assert candidate.original_code == stored_original
    assert candidate.repaired_code == proposed
    assert candidate.evidence
    assert "AssertionError" in orchestrator.request.prompt
    assert orchestrator.provider_name == "auto"
    assert target.read_bytes().decode("utf-8") == stored_original


def test_repair_candidate_rejects_missing_source_and_unsupported_types(tmp_path):
    service = SelfHealingService(orchestrator=FakeOrchestrator("{}"))
    request = _repair_request(tmp_path)
    with pytest.raises(FileNotFoundError):
        asyncio.run(service.repair(request))

    unsupported = tmp_path / "tests" / "test_sample.txt"
    unsupported.parent.mkdir()
    unsupported.write_text("source", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        asyncio.run(
            service.repair(_repair_request(tmp_path, "tests/test_sample.txt"))
        )


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"repaired_code": "", "explanation": "x", "changes": ["x"]}),
        json.dumps({"repaired_code": "bad syntax !", "explanation": "x", "changes": ["x"]}),
    ],
)
def test_repair_candidate_rejects_malformed_and_invalid_provider_output(
    tmp_path,
    content,
):
    target = tmp_path / "tests" / "test_sample.py"
    target.parent.mkdir()
    target.write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    service = SelfHealingService(orchestrator=FakeOrchestrator(content))

    with pytest.raises(ValueError):
        asyncio.run(service.repair(_repair_request(tmp_path)))

    assert target.read_text(encoding="utf-8") == "def test_sample():\n    assert True\n"


def test_repair_candidate_handles_provider_failure_without_leaking_details(tmp_path):
    target = tmp_path / "tests" / "test_sample.py"
    target.parent.mkdir()
    target.write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    service = SelfHealingService(
        orchestrator=FakeOrchestrator(RuntimeError("token=private-value"))
    )

    with pytest.raises(RuntimeError, match="generation failed") as error:
        asyncio.run(service.repair(_repair_request(tmp_path)))
    assert "private-value" not in str(error.value)


def test_repair_candidate_rejects_insufficient_analysis(tmp_path):
    execution = _execution().model_copy(update={"repository_path": str(tmp_path)})
    analysis = analyze_failure(
        _analysis_request(
            execution.model_copy(
                update={
                    "stderr": "",
                    "stdout": "",
                    "error": None,
                    "status": ExecutionStatus.FAILED,
                }
            )
        )
    )
    with pytest.raises(ValidationError, match="does not support"):
        SelfHealingRequest(
            repository_path=str(tmp_path),
            execution=execution,
            analysis=analysis,
        )


def test_repair_file_service_requires_approval_and_applies_once(tmp_path):
    target = tmp_path / "sample.py"
    original = "before = True\n"
    proposed = "after = True\n"
    target.write_text(original, encoding="utf-8")
    stored_original = target.read_bytes().decode("utf-8")
    service = RepairFileService()
    service.register_candidate("repair-one", str(tmp_path), "sample.py", stored_original, proposed)

    with pytest.raises(ValueError, match="Explicit approval"):
        service.apply_repair("repair-one", approved=False)
    code, relative = service.apply_repair("repair-one", approved=True)
    assert code == proposed
    assert relative == "sample.py"
    assert target.read_text(encoding="utf-8") == proposed

    with pytest.raises(ValueError, match="already been applied"):
        service.apply_repair("repair-one", approved=True)


def test_repair_file_service_rejects_traversal_and_changed_target(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("outside\n", encoding="utf-8")
    with pytest.raises(ValueError, match="repository-relative"):
        RepairFileService().register_candidate(
            "traversal",
            str(tmp_path),
            "../outside.py",
            "outside\n",
            "changed\n",
        )

    target = tmp_path / "sample.py"
    target.write_text("before\n", encoding="utf-8")
    stored_original = target.read_bytes().decode("utf-8")
    service = RepairFileService()
    service.register_candidate("conflict", str(tmp_path), "sample.py", stored_original, "after\n")
    target.write_text("newer user edit\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after review"):
        service.apply_repair("conflict", approved=True)
    assert target.read_text(encoding="utf-8") == "newer user edit\n"


def test_repair_file_service_restores_only_if_target_has_no_newer_changes(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("before\n", encoding="utf-8")
    stored_original = target.read_bytes().decode("utf-8")
    service = RepairFileService()
    service.register_candidate("restore-one", str(tmp_path), "sample.py", stored_original, "after\n")
    service.apply_repair("restore-one", approved=True)
    restored, relative = service.restore_backup("restore-one")
    assert restored == stored_original
    assert relative == "sample.py"
    assert target.read_bytes().decode("utf-8") == stored_original
    with pytest.raises(ValueError, match="Only an applied repair"):
        service.restore_backup("restore-one")

    service.register_candidate("restore-conflict", str(tmp_path), "sample.py", stored_original, "after\n")
    service.apply_repair("restore-conflict", approved=True)
    target.write_text("new user edit\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after application"):
        service.restore_backup("restore-conflict")
    assert target.read_text(encoding="utf-8") == "new user edit\n"


def test_repair_file_service_reports_failed_write_without_changing_original(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "sample.py"
    target.write_text("before\n", encoding="utf-8")
    stored_original = target.read_bytes().decode("utf-8")
    service = RepairFileService()
    service.register_candidate("write-failure", str(tmp_path), "sample.py", stored_original, "after\n")

    def fail_write(target_path, content, file_mode):
        assert target_path == target
        assert content == b"after\n"
        assert file_mode == target.stat().st_mode
        raise OSError("disk unavailable")

    monkeypatch.setattr(service, "_atomic_write", fail_write)
    with pytest.raises(OSError, match="disk unavailable"):
        service.apply_repair("write-failure", approved=True)
    assert target.read_bytes().decode("utf-8") == stored_original
