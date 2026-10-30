import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.execution.models import (
    ExecutionFramework,
    ExecutionRequest,
    ExecutionStatus,
)
from app.execution.process_manager import ProcessManager, ProcessResult
from app.execution.pytest_executor import PytestExecutor
from app.execution.result_registry import execution_result_registry
from app.execution.playwright_executor import PlaywrightExecutor
from app.execution.selenium_executor import SeleniumExecutor
from app.execution.validation import execution_status
from app.api.v1 import execution as execution_api
from app.main import app


class FakeProcessManager:
    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.call: dict | None = None

    async def run(self, **kwargs) -> ProcessResult:
        self.call = kwargs
        return self.result


def _process(
    *,
    exit_code: int | None = 0,
    stdout: str = "1 passed",
    stderr: str = "",
    timed_out: bool = False,
    error: str | None = None,
) -> ProcessResult:
    return ProcessResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.25,
        timed_out=timed_out,
        error=error,
    )


def _pytest_file(repository: Path) -> Path:
    tests = repository / "tests"
    tests.mkdir(exist_ok=True)
    test_file = tests / "test_sample.py"
    test_file.write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    return test_file


def test_pytest_executor_runs_selected_file_in_repository(
    tmp_path,
    monkeypatch,
):
    test_file = _pytest_file(tmp_path)
    process_manager = FakeProcessManager(_process())
    monkeypatch.setattr(
        "app.execution.pytest_executor.importlib.util.find_spec",
        lambda module: object() if module == "pytest" else None,
    )

    result = asyncio.run(
        PytestExecutor(process_manager).execute(
            str(tmp_path),
            "tests/test_sample.py",
            timeout_seconds=17,
        )
    )

    assert result.status == ExecutionStatus.PASSED
    assert result.file_path == "tests/test_sample.py"
    assert result.exit_code == 0
    assert result.duration_seconds == 0.25
    assert process_manager.call["cwd"] == str(tmp_path)
    assert process_manager.call["command"][-1] == "tests/test_sample.py"
    assert process_manager.call["timeout_seconds"] == 17
    assert test_file.exists()


def test_pytest_executor_reports_failed_skipped_timeout_and_runner_error(
    tmp_path,
    monkeypatch,
):
    _pytest_file(tmp_path)
    monkeypatch.setattr(
        "app.execution.pytest_executor.importlib.util.find_spec",
        lambda _module: object(),
    )

    failed = asyncio.run(PytestExecutor(
        FakeProcessManager(_process(exit_code=1, stdout="1 failed"))
    ).execute(str(tmp_path), "tests/test_sample.py"))
    skipped = asyncio.run(PytestExecutor(
        FakeProcessManager(_process(stdout="1 skipped"))
    ).execute(str(tmp_path), "tests/test_sample.py"))
    timed_out = asyncio.run(PytestExecutor(
        FakeProcessManager(
            _process(exit_code=-9, timed_out=True, error="timeout")
        )
    ).execute(str(tmp_path), "tests/test_sample.py"))
    runner_error = asyncio.run(PytestExecutor(
        FakeProcessManager(
            _process(exit_code=None, stdout="", error="unavailable")
        )
    ).execute(str(tmp_path), "tests/test_sample.py"))

    assert failed.status == ExecutionStatus.FAILED
    assert skipped.status == ExecutionStatus.SKIPPED
    assert timed_out.status == ExecutionStatus.TIMEOUT
    assert runner_error.status == ExecutionStatus.ERROR


def test_pytest_executor_reports_missing_runner_and_rejects_unsafe_paths(
    tmp_path,
    monkeypatch,
):
    _pytest_file(tmp_path)
    manager = FakeProcessManager(_process())
    monkeypatch.setattr(
        "app.execution.pytest_executor.importlib.util.find_spec",
        lambda _module: None,
    )
    result = asyncio.run(
        PytestExecutor(manager).execute(
            str(tmp_path),
            "tests/test_sample.py",
        )
    )
    assert result.status == ExecutionStatus.ERROR
    assert "not installed" in result.error
    assert manager.call is None

    with pytest.raises(ValueError, match="traversal|escapes"):
        asyncio.run(
            PytestExecutor(manager).execute(
                str(tmp_path),
                "../outside/test_sample.py",
            )
        )
    with pytest.raises(ValueError, match="compatible"):
        (tmp_path / "tests" / "invalid.py").write_text("", encoding="utf-8")
        asyncio.run(
            PytestExecutor(manager).execute(
                str(tmp_path),
                "tests/invalid.py",
            )
        )


def _playwright_project(repository: Path, *, with_runner: bool = True) -> Path:
    project = repository / "web"
    (project / "tests").mkdir(parents=True)
    (project / "package.json").write_text(
        json.dumps({"devDependencies": {"@playwright/test": "1.0.0"}}),
        encoding="utf-8",
    )
    test_file = project / "tests" / "sample.spec.ts"
    test_file.write_text('import { test } from "@playwright/test";\n', encoding="utf-8")
    if with_runner:
        runner = project / "node_modules" / "@playwright" / "test"
        runner.mkdir(parents=True)
        (runner / "cli.js").write_text("/* local test stub */", encoding="utf-8")
    return test_file


def test_playwright_executor_uses_local_runner_and_captures_result(
    tmp_path,
    monkeypatch,
):
    _playwright_project(tmp_path)
    monkeypatch.setattr("app.execution.playwright_executor.shutil.which", lambda _name: "node")
    manager = FakeProcessManager(
        _process(stdout="1 passed", stderr="runner note")
    )

    result = asyncio.run(
        PlaywrightExecutor(manager).execute(
            str(tmp_path),
            "web/tests/sample.spec.ts",
        )
    )

    assert result.status == ExecutionStatus.PASSED
    assert result.framework == ExecutionFramework.PLAYWRIGHT
    assert result.stdout == "1 passed"
    assert result.stderr == "runner note"
    assert manager.call["cwd"] == str(tmp_path / "web")
    assert manager.call["command"][1].endswith("cli.js")
    assert manager.call["command"][-1] == "tests/sample.spec.ts"
    assert "npx" not in manager.call["command"]


def test_playwright_executor_reports_failures_missing_runner_and_timeouts(
    tmp_path,
    monkeypatch,
):
    _playwright_project(tmp_path)
    monkeypatch.setattr("app.execution.playwright_executor.shutil.which", lambda _name: "node")

    failed = asyncio.run(PlaywrightExecutor(
        FakeProcessManager(_process(exit_code=1, stdout="1 failed"))
    ).execute(str(tmp_path), "web/tests/sample.spec.ts"))
    timed_out = asyncio.run(PlaywrightExecutor(
        FakeProcessManager(_process(exit_code=-9, timed_out=True, error="timeout"))
    ).execute(str(tmp_path), "web/tests/sample.spec.ts"))
    runner_error = asyncio.run(PlaywrightExecutor(
        FakeProcessManager(
            _process(exit_code=None, stdout="", error="could not start")
        )
    ).execute(str(tmp_path), "web/tests/sample.spec.ts"))
    assert failed.status == ExecutionStatus.FAILED
    assert timed_out.status == ExecutionStatus.TIMEOUT
    assert runner_error.status == ExecutionStatus.ERROR

    no_runner_root = tmp_path / "missing"
    _playwright_project(no_runner_root, with_runner=False)
    missing_runner = asyncio.run(
        PlaywrightExecutor().execute(
            str(no_runner_root),
            "web/tests/sample.spec.ts",
        )
    )
    assert missing_runner.status == ExecutionStatus.ERROR
    assert "local Playwright runner" in missing_runner.error


def test_playwright_executor_rejects_invalid_file_and_incompatible_project(
    tmp_path,
    monkeypatch,
):
    _playwright_project(tmp_path)
    manager = FakeProcessManager(_process())
    monkeypatch.setattr("app.execution.playwright_executor.shutil.which", lambda _name: "node")

    with pytest.raises(ValueError, match="compatible"):
        (tmp_path / "web" / "tests" / "test_sample.py").write_text(
            "", encoding="utf-8"
        )
        asyncio.run(
            PlaywrightExecutor(manager).execute(
                str(tmp_path),
                "web/tests/test_sample.py",
            )
        )

    other_project = tmp_path / "other"
    (other_project / "tests").mkdir(parents=True)
    (other_project / "tests" / "test_missing.spec.ts").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="package.json"):
        asyncio.run(
            PlaywrightExecutor(manager).execute(
                str(tmp_path),
                "other/tests/test_missing.spec.ts",
            )
        )

    malformed_project = tmp_path / "malformed"
    malformed_test = _playwright_project(malformed_project)
    (malformed_project / "web" / "package.json").write_text(
        json.dumps({"dependencies": None}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="dependencies must be an object"):
        asyncio.run(
            PlaywrightExecutor(manager).execute(
                str(malformed_project),
                malformed_test.relative_to(malformed_project).as_posix(),
            )
        )


def test_selenium_executor_runs_python_tests_with_pytest(
    tmp_path,
    monkeypatch,
):
    _pytest_file(tmp_path)
    (tmp_path / "requirements.txt").write_text("selenium==4.20.0\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.execution.selenium_executor.importlib.util.find_spec",
        lambda module: object() if module in {"pytest", "selenium"} else None,
    )
    manager = FakeProcessManager(_process(stdout="1 passed"))

    result = asyncio.run(
        SeleniumExecutor(manager).execute(
            str(tmp_path),
            "tests/test_sample.py",
        )
    )

    assert result.status == ExecutionStatus.PASSED
    assert result.framework == ExecutionFramework.SELENIUM
    assert manager.call["command"][1:3] == ["-m", "pytest"]
    assert manager.call["cwd"] == str(tmp_path)


def test_selenium_executor_requires_project_selenium_evidence(
    tmp_path,
    monkeypatch,
):
    _pytest_file(tmp_path)
    monkeypatch.setattr(
        "app.execution.selenium_executor.importlib.util.find_spec",
        lambda _module: object(),
    )
    manager = FakeProcessManager(_process())

    with pytest.raises(ValueError, match="Selenium dependency or import evidence"):
        asyncio.run(
            SeleniumExecutor(manager).execute(
                str(tmp_path),
                "tests/test_sample.py",
            )
        )

    assert manager.call is None


def test_selenium_executor_reports_missing_dependencies_and_process_results(
    tmp_path,
    monkeypatch,
):
    _pytest_file(tmp_path)
    (tmp_path / "requirements.txt").write_text("selenium==4.20.0\n", encoding="utf-8")
    manager = FakeProcessManager(
        _process(exit_code=1, stdout="1 failed", stderr="WebDriver error")
    )
    monkeypatch.setattr(
        "app.execution.selenium_executor.importlib.util.find_spec",
        lambda module: object() if module == "pytest" else None,
    )
    missing = asyncio.run(
        SeleniumExecutor(manager).execute(
            str(tmp_path),
            "tests/test_sample.py",
        )
    )
    assert missing.status == ExecutionStatus.ERROR
    assert "Selenium is not installed" in missing.error
    assert manager.call is None

    monkeypatch.setattr(
        "app.execution.selenium_executor.importlib.util.find_spec",
        lambda _module: object(),
    )
    failed = asyncio.run(SeleniumExecutor(manager).execute(
        str(tmp_path),
        "tests/test_sample.py",
    ))
    timeout = asyncio.run(SeleniumExecutor(
        FakeProcessManager(_process(exit_code=-9, timed_out=True, error="timeout"))
    ).execute(str(tmp_path), "tests/test_sample.py"))
    runner_error = asyncio.run(SeleniumExecutor(
        FakeProcessManager(
            _process(exit_code=None, stderr="startup", error="startup failed")
        )
    ).execute(str(tmp_path), "tests/test_sample.py"))
    assert failed.status == ExecutionStatus.FAILED
    assert failed.stderr == "WebDriver error"
    assert timeout.status == ExecutionStatus.TIMEOUT
    assert runner_error.status == ExecutionStatus.ERROR


def test_selenium_executor_classifies_browser_initialization_failure_as_error():
    result = execution_status(
        _process(
            exit_code=1,
            stdout="",
            stderr="selenium.common.exceptions.SessionNotCreatedException",
        ),
        ExecutionFramework.SELENIUM,
    )

    assert result == ExecutionStatus.ERROR


def test_success_status_uses_exit_code_and_rejects_contradictory_failure_output():
    passed = execution_status(
        _process(exit_code=0, stdout="1 passed"),
        ExecutionFramework.PYTEST,
    )
    contradictory = execution_status(
        _process(exit_code=0, stdout="1 failed"),
        ExecutionFramework.PYTEST,
    )

    assert passed == ExecutionStatus.PASSED
    assert contradictory == ExecutionStatus.ERROR


def test_execution_request_rejects_arbitrary_runner_arguments():
    with pytest.raises(ValueError, match="runner options"):
        ExecutionRequest(
            repository_path="repo",
            file_path="tests/test_sample.py",
            framework="pytest",
            args=["--rootdir=C:\\outside"],
        )


def test_process_manager_redacts_environment_secrets(monkeypatch, tmp_path):
    class CompletedProcess:
        returncode = 0

        async def communicate(self):
            return b"token=private-value", b"private-value"

    async def start_process(*_args, **_kwargs):
        return CompletedProcess()

    monkeypatch.setattr(
        "app.execution.process_manager.asyncio.create_subprocess_exec",
        start_process,
    )
    result = asyncio.run(
        ProcessManager().run(
            ["python", "-c", "pass"],
            str(tmp_path),
            1,
            env={"SERVICE_TOKEN": "private-value"},
        )
    )

    assert result.stdout == "token=[REDACTED]"
    assert result.stderr == "[REDACTED]"


def test_process_manager_reports_timeout_and_startup_errors(monkeypatch, tmp_path):
    class HangingProcess:
        returncode = None

        def __init__(self):
            self.killed = False

        async def communicate(self):
            if not self.killed:
                await asyncio.sleep(1)
            return b"partial output", b""

        def kill(self):
            self.killed = True
            self.returncode = -9

    async def start_hanging_process(*_args, **_kwargs):
        return HangingProcess()

    monkeypatch.setattr(
        "app.execution.process_manager.asyncio.create_subprocess_exec",
        start_hanging_process,
    )
    timeout_result = asyncio.run(
        ProcessManager().run(["python"], str(tmp_path), 0.01)
    )
    assert timeout_result.timed_out is True
    assert timeout_result.stdout == "partial output"

    async def fail_to_start(*_args, **_kwargs):
        raise OSError("credential=private-value")

    monkeypatch.setattr(
        "app.execution.process_manager.asyncio.create_subprocess_exec",
        fail_to_start,
    )
    startup_result = asyncio.run(
        ProcessManager().run(["missing-runner"], str(tmp_path), 1)
    )
    assert startup_result.error == "Test runner could not be started."
    assert "private-value" not in startup_result.error


def test_execution_api_routes_to_selected_engine_and_validates_request(
    monkeypatch,
    tmp_path,
):
    test_file = _pytest_file(tmp_path)
    result = {
        "repository_path": str(tmp_path),
        "file_path": "tests/test_sample.py",
        "framework": "pytest",
        "status": "passed",
        "exit_code": 0,
        "stdout": "1 passed",
        "stderr": "",
        "duration_seconds": 0.25,
        "error": None,
    }

    async def execute(**kwargs):
        if kwargs["file_path"] != "tests/test_sample.py":
            raise ValueError("Test file path must be relative to the repository.")
        return result

    async def override_db():
        yield object()

    async def persist_execution(*_args, **_kwargs):
        return None

    async def persist_commit(*_args, **_kwargs):
        return None

    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    monkeypatch.setattr(
        execution_api.testing_persistence_service,
        "save_execution",
        persist_execution,
    )
    monkeypatch.setattr(
        execution_api.testing_persistence_service,
        "commit",
        persist_commit,
    )
    monkeypatch.setattr(execution_api.pytest_executor, "execute", execute)
    with TestClient(app) as client:
        response = client.post(
            "/execution/run",
            json={
                "repository_path": str(tmp_path),
                "file_path": "tests/test_sample.py",
                "framework": "pytest",
            },
        )
        invalid = client.post(
            "/execution/run",
            json={
                "repository_path": str(tmp_path),
                "file_path": str(test_file),
                "framework": "pytest",
            },
        )
        async def fail_without_disclosing_details(**_kwargs):
            raise RuntimeError("credential=secret-value")

        monkeypatch.setattr(
            execution_api.pytest_executor,
            "execute",
            fail_without_disclosing_details,
        )
        failed = client.post(
            "/execution/run",
            json={
                "repository_path": str(tmp_path),
                "file_path": "tests/test_sample.py",
                "framework": "pytest",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "passed"
    assert invalid.status_code == 400
    assert failed.status_code == 500
    assert failed.json()["detail"] == "Test execution could not be completed."
    assert "secret-value" not in failed.text


def test_execution_api_does_not_report_success_when_history_persistence_fails(
    monkeypatch,
    tmp_path,
):
    _pytest_file(tmp_path)
    execution_id = "persist-failure-test"
    result = {
        "execution_id": execution_id,
        "repository_path": str(tmp_path),
        "file_path": "tests/test_sample.py",
        "framework": "pytest",
        "status": "passed",
        "exit_code": 0,
        "stdout": "1 passed",
        "stderr": "",
        "duration_seconds": 0.25,
        "error": None,
    }

    async def execute(**_kwargs):
        return result

    async def override_db():
        yield object()

    async def save_execution(*_args, **_kwargs):
        return None

    async def fail_commit(*_args, **_kwargs):
        raise RuntimeError("simulated persistence failure")

    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    monkeypatch.setattr(execution_api.pytest_executor, "execute", execute)
    monkeypatch.setattr(
        execution_api.testing_persistence_service,
        "save_execution",
        save_execution,
    )
    monkeypatch.setattr(
        execution_api.testing_persistence_service,
        "commit",
        fail_commit,
    )

    with TestClient(app) as client:
        response = client.post(
            "/execution/run",
            json={
                "repository_path": str(tmp_path),
                "file_path": "tests/test_sample.py",
                "framework": "pytest",
            },
        )

    assert response.status_code == 500
    assert execution_result_registry.get(execution_id) is None
