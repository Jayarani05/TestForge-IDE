import re
from pathlib import Path, PureWindowsPath

from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
    ExecutionStatus,
)
from app.execution.process_manager import ProcessResult


def resolve_test_file(
    repository_path: str,
    file_path: str,
    framework: ExecutionFramework,
) -> tuple[Path, Path, str]:
    repository = Path(repository_path).expanduser().resolve()
    if not repository.exists() or not repository.is_dir():
        raise ValueError("Selected repository must be an existing directory.")

    windows_path = PureWindowsPath(file_path)
    relative_file = Path(file_path)
    if (
        not file_path.strip()
        or relative_file.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
    ):
        raise ValueError("Test file path must be relative to the repository.")
    if any(part == ".." for part in re.split(r"[\\/]", file_path)):
        raise ValueError("Test file path cannot contain traversal components.")

    test_path = (repository / relative_file).resolve()
    try:
        relative_path = test_path.relative_to(repository).as_posix()
    except ValueError as exc:
        raise ValueError("Test file path escapes the repository.") from exc

    if not test_path.exists():
        raise ValueError("Selected test file does not exist.")
    if not test_path.is_file():
        raise ValueError("Selected test path is not a file.")

    if framework in {ExecutionFramework.PYTEST, ExecutionFramework.SELENIUM}:
        eligible = (
            test_path.suffix.lower() == ".py"
            and (
                test_path.name.startswith("test_")
                or test_path.name.endswith("_test.py")
            )
        )
    else:
        eligible = (
            test_path.suffix.lower() in {".js", ".cjs", ".mjs", ".ts"}
            and re.search(r"\.(?:spec|test)\.(?:js|cjs|mjs|ts)$", test_path.name)
            is not None
        )
    if not eligible:
        raise ValueError(
            f"Selected file is not a compatible {framework.value} test file."
        )

    return repository, test_path, relative_path


def execution_status(
    result: ProcessResult,
    framework: ExecutionFramework,
) -> ExecutionStatus:
    if result.timed_out:
        return ExecutionStatus.TIMEOUT
    if result.error or result.exit_code is None:
        return ExecutionStatus.ERROR
    if result.exit_code == 0:
        output = f"{result.stdout}\n{result.stderr}"
        failed = re.search(
            r"\b([1-9]\d*)\s+(?:failed|failures?)\b",
            output,
            re.IGNORECASE,
        )
        if failed:
            return ExecutionStatus.ERROR
        skipped = re.search(r"\b\d+\s+skipped\b", output, re.IGNORECASE)
        passed = re.search(
            r"\b([1-9]\d*)\s+(?:passed|pass)\b",
            output,
            re.IGNORECASE,
        )
        if skipped and not passed:
            return ExecutionStatus.SKIPPED
        return ExecutionStatus.PASSED
    if result.exit_code == 1:
        output = f"{result.stdout}\n{result.stderr}".lower()
        missing_runner_indicators = (
            "no module named pytest",
            "no module named selenium",
            "command not found",
            "not recognized as an internal or external command",
            "could not determine executable to run",
        )
        browser_initialization_indicators = {
            ExecutionFramework.PLAYWRIGHT: (
                "browserType.launch",
                "executable doesn't exist",
                "failed to launch",
                "browser has been closed",
            ),
            ExecutionFramework.SELENIUM: (
                "webdriverexception",
                "sessionnotcreatedexception",
                "unable to obtain driver",
                "selenium.common.exceptions",
            ),
            ExecutionFramework.PYTEST: (),
        }
        if any(indicator in output for indicator in missing_runner_indicators) or any(
            indicator.lower() in output
            for indicator in browser_initialization_indicators[framework]
        ):
            return ExecutionStatus.ERROR
        return ExecutionStatus.FAILED
    return ExecutionStatus.ERROR


def result_from_process(
    repository: Path,
    relative_path: str,
    framework: ExecutionFramework,
    process_result: ProcessResult,
) -> ExecutionResult:
    return ExecutionResult(
        repository_path=str(repository),
        file_path=relative_path,
        framework=framework,
        status=execution_status(process_result, framework),
        exit_code=process_result.exit_code,
        stdout=process_result.stdout,
        stderr=process_result.stderr,
        duration_seconds=process_result.duration_seconds,
        error=process_result.error,
    )


def execution_error_result(
    repository: Path,
    relative_path: str,
    framework: ExecutionFramework,
    message: str,
) -> ExecutionResult:
    return ExecutionResult(
        repository_path=str(repository),
        file_path=relative_path,
        framework=framework,
        status=ExecutionStatus.ERROR,
        error=message,
    )
