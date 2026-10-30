import importlib.util
import re
from pathlib import Path

from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
)
from app.execution.process_manager import ProcessManager
from app.execution.validation import (
    execution_error_result,
    resolve_test_file,
)
from app.execution.pytest_executor import PytestExecutor


class SeleniumExecutor:
    """Runs Python Selenium tests through pytest; it never starts a browser itself."""

    framework = ExecutionFramework.SELENIUM

    def __init__(
        self,
        process_manager: ProcessManager | None = None,
    ) -> None:
        self.process_manager = process_manager or ProcessManager()
        self.pytest_executor = PytestExecutor(self.process_manager)

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
        if importlib.util.find_spec("selenium") is None:
            return execution_error_result(
                repository,
                relative_path,
                self.framework,
                "Selenium is not installed in the selected execution environment.",
            )
        if not self._has_selenium_evidence(repository, test_path):
            raise ValueError(
                "No Selenium dependency or import evidence was found for this project."
            )

        result = await self.pytest_executor.execute(
            repository_path=repository_path,
            file_path=file_path,
            timeout_seconds=timeout_seconds,
            args=args,
            measure_coverage=measure_coverage,
        )
        return result.model_copy(
            update={"framework": self.framework}
        )

    @staticmethod
    def _has_selenium_evidence(
        repository: Path,
        test_path: Path,
    ) -> bool:
        evidence_files = {
            test_path,
            *(
                parent / "conftest.py"
                for parent in (test_path.parent, *test_path.parent.parents)
                if parent == repository or repository in parent.parents
            ),
        }
        for parent in (test_path.parent, *test_path.parent.parents):
            if parent == repository or repository in parent.parents:
                evidence_files.update(
                    parent / name
                    for name in (
                        "requirements.txt",
                        "requirements-dev.txt",
                        "pyproject.toml",
                        "setup.py",
                        "Pipfile",
                    )
                )
            if parent == repository:
                break

        for evidence_file in evidence_files:
            if not evidence_file.is_file():
                continue
            try:
                source = evidence_file.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue
            if evidence_file in {test_path} or evidence_file.name == "conftest.py":
                if re.search(r"\b(?:from|import)\s+selenium\b", source):
                    return True
            elif re.search(r"\bselenium(?:-webdriver)?\b", source, re.IGNORECASE):
                return True
        return False
