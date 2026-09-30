from pathlib import Path

from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
    ExecutionStatus,
)
from app.execution.process_manager import ProcessManager


class PlaywrightExecutor:
    """Executes Playwright tests through the Playwright CLI."""

    framework = ExecutionFramework.PLAYWRIGHT

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

        playwright_project = repository / "desktop"

        if not playwright_project.exists():
            raise ValueError(
                f"Playwright project directory does not exist: "
                f"{playwright_project}"
            )

        package_json = playwright_project / "package.json"

        if not package_json.exists():
            raise ValueError(
                f"Playwright project does not contain package.json: "
                f"{package_json}"
            )

        try:
            relative_test_path = test_path.relative_to(
                playwright_project
            )

            playwright_test_path = relative_test_path.as_posix()
        except ValueError as exc:
            raise ValueError(
                "Playwright test file must be inside the "
                "desktop project."
            ) from exc

        extra_args = args or []

        command = [
            "npx",
            "playwright",
            "test",
            playwright_test_path,
            *extra_args,
        ]

        # print("PLAYWRIGHT COMMAND:", command)
        # print("PLAYWRIGHT CWD:", playwright_project)
        # print("PLAYWRIGHT TEST EXISTS:", test_path.exists())
        # print("PLAYWRIGHT TEST PATH:", test_path)
        # print("PLAYWRIGHT RELATIVE PATH:", relative_test_path)

        process_result = await self.process_manager.run(
            command=command,
            cwd=str(playwright_project),
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