import importlib.util
import sys
import tempfile
from pathlib import Path

from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
)
from app.execution.coverage import (
    TRACE_RUNNER_SCRIPT,
    measure_python_statement_coverage,
    parse_trace_counts,
    source_digest,
)
from app.execution.process_manager import ProcessManager
from app.execution.validation import (
    execution_error_result,
    resolve_test_file,
    result_from_process,
)


class PytestExecutor:
    """Executes a selected Python pytest file inside its repository."""

    framework = ExecutionFramework.PYTEST

    def __init__(
        self,
        process_manager: ProcessManager | None = None,
    ) -> None:
        self.process_manager = process_manager or ProcessManager()

    async def execute(
        self,
        repository_path: str,
        file_path: str,
        timeout_seconds: int = 120,
        args: list[str] | None = None,
        measure_coverage: bool = False,
    ) -> ExecutionResult:
        repository, test_path, relative_path = resolve_test_file(
            repository_path,
            file_path,
            self.framework,
        )
        if importlib.util.find_spec("pytest") is None:
            return execution_error_result(
                repository,
                relative_path,
                self.framework,
                "Pytest is not installed in the selected execution environment.",
            )

        execution_root = repository
        backend_directory = repository / "backend"
        if (
            backend_directory.is_dir()
            and (backend_directory / "app").is_dir()
            and test_path.is_relative_to(backend_directory)
        ):
            execution_root = backend_directory

        execution_file = test_path.relative_to(execution_root).as_posix()
        command = [sys.executable, "-m", "pytest", execution_file, *(args or [])]
        measured_source_digest = None
        coverage_error = None
        if measure_coverage:
            try:
                measured_source_digest = source_digest(repository)
            except OSError:
                coverage_error = "Repository Python source could not be read for coverage."

        if not measure_coverage or coverage_error or measured_source_digest is None:
            process_result = await self.process_manager.run(
                command=command,
                cwd=str(execution_root),
                timeout_seconds=timeout_seconds,
                env={"PYTHONPATH": str(execution_root)},
            )
            execution = result_from_process(
                repository,
                relative_path,
                self.framework,
                process_result,
            )
            if measure_coverage:
                return execution.model_copy(
                    update={
                        "coverage_error": coverage_error
                        or "No production Python source files were found to measure.",
                        "source_digest": measured_source_digest,
                    }
                )
            return execution

        with tempfile.TemporaryDirectory(prefix="testforge-coverage-") as directory:
            coverage_path = str(Path(directory) / "trace.json")
            process_result = await self.process_manager.run(
                command=[
                    sys.executable,
                    "-c",
                    TRACE_RUNNER_SCRIPT,
                    coverage_path,
                    str(repository),
                    execution_file,
                    *(args or []),
                ],
                cwd=str(execution_root),
                timeout_seconds=timeout_seconds,
                env={"PYTHONPATH": str(execution_root)},
            )
            try:
                counts = parse_trace_counts(Path(coverage_path))
                measurement = measure_python_statement_coverage(
                    repository,
                    counts,
                )
            except (OSError, ValueError, SyntaxError):
                measurement = None
                coverage_error = "Python coverage output could not be validated."
            if measurement is None and coverage_error is None:
                coverage_error = "No executable production Python statements were measured."

        execution = result_from_process(
            repository,
            relative_path,
            self.framework,
            process_result,
        )
        return execution.model_copy(
            update={
                "coverage_percent": (
                    measurement.percentage if measurement is not None else None
                ),
                "coverage_covered_statements": (
                    measurement.covered_statements if measurement is not None else None
                ),
                "coverage_total_statements": (
                    measurement.total_statements if measurement is not None else None
                ),
                "coverage_error": coverage_error,
                "source_digest": measured_source_digest,
            }
        )
