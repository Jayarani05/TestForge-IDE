from pathlib import Path

from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
    ExecutionStatus,
)
from app.execution.process_manager import ProcessManager


class SeleniumExecutor:
    """Executes Selenium tests through the Python test runner."""

    framework = ExecutionFramework.SELENIUM

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
    ) -> ExecutionResult:
        repository = Path(repository_path).resolve()
        test_file = Path(file_path)

        if test_file.is_absolute():
            raise ValueError(
                "Test file path must be relative to the repository."
            )

        test_path = (repository / test_file).resolve()

        try:
            test_path.relative_to(repository)
        except ValueError as exc:
            raise ValueError(
                "Test file path escapes the repository."
            ) from exc

        if not test_path.exists():
            raise ValueError(
                f"Test file does not exist: {file_path}"
            )

        if not test_path.is_file():
            raise ValueError(
                f"Test path is not a file: {file_path}"
            )

        extra_args = args or []

        python_executable = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"

        if not python_executable.exists():
            raise ValueError(
                f"Backend Python environment not found: {python_executable}"
        )

        command = [
            str(python_executable),
            str(test_path.relative_to(repository)),
            *extra_args,
        ]

        process_result = await self.process_manager.run(
            command=command,
            cwd=str(repository),
            timeout_seconds=timeout_seconds,
        )

        if process_result.timed_out:
            status = ExecutionStatus.TIMEOUT

        elif process_result.error:
            status = ExecutionStatus.ERROR

        elif process_result.exit_code == 0:
            status = ExecutionStatus.PASSED

        else:
            status = ExecutionStatus.FAILED

        return ExecutionResult(
            repository_path=str(repository),
            file_path=str(test_path.relative_to(repository)),
            framework=self.framework,
            status=status,
            exit_code=process_result.exit_code,
            stdout=process_result.stdout,
            stderr=process_result.stderr,
            duration_seconds=process_result.duration_seconds,
            error=process_result.error,
        )