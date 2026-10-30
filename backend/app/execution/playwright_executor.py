import json
import shutil
from pathlib import Path

from app.execution.models import (
    ExecutionFramework,
    ExecutionResult,
)
from app.execution.process_manager import ProcessManager
from app.execution.validation import (
    execution_error_result,
    resolve_test_file,
    result_from_process,
)


class PlaywrightExecutor:
    """Executes a selected Playwright test using the project's local runner."""

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
        measure_coverage: bool = False,
    ) -> ExecutionResult:
        repository, test_path, relative_path = resolve_test_file(
            repository_path,
            file_path,
            self.framework,
        )
        if args:
            raise ValueError("Additional Playwright runner options are not supported.")

        project_root = self._find_project_root(repository, test_path)
        if project_root is None:
            raise ValueError(
                "Selected Playwright test must belong to a project with package.json."
            )

        package_file = project_root / "package.json"
        try:
            package_data = json.loads(package_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Playwright project package.json is invalid.") from exc

        if not isinstance(package_data, dict):
            raise ValueError("Playwright project package.json must contain an object.")
        dependencies: dict[str, object] = {}
        for field in ("dependencies", "devDependencies"):
            field_dependencies = package_data.get(field, {})
            if not isinstance(field_dependencies, dict):
                raise ValueError(
                    f"Playwright project package.json field {field} must be an object."
                )
            dependencies.update(field_dependencies)
        configured = (
            "@playwright/test" in dependencies
            or "playwright" in dependencies
            or any(project_root.glob("playwright.config.*"))
        )
        if not configured:
            raise ValueError(
                "No Playwright dependency or project configuration was detected."
            )

        local_runner = (
            project_root / "node_modules" / "@playwright" / "test" / "cli.js"
        )
        if not local_runner.is_file():
            local_runner = project_root / "node_modules" / "playwright" / "cli.js"
        try:
            local_runner.resolve().relative_to(project_root.resolve())
        except ValueError:
            return execution_error_result(
                repository,
                relative_path,
                self.framework,
                "The local Playwright runner must be inside the selected project.",
            )
        node = shutil.which("node")
        if not node or not local_runner.is_file():
            return execution_error_result(
                repository,
                relative_path,
                self.framework,
                "The local Playwright runner is unavailable. Install it in this "
                "project before running tests.",
            )

        runner_test_path = test_path.relative_to(project_root).as_posix()
        process_result = await self.process_manager.run(
            command=[
                node,
                str(local_runner),
                "test",
                runner_test_path,
            ],
            cwd=str(project_root),
            timeout_seconds=timeout_seconds,
        )
        result = result_from_process(
            repository,
            relative_path,
            self.framework,
            process_result,
        )
        if measure_coverage:
            return result.model_copy(
                update={
                    "coverage_error": (
                        "Coverage measurement is not available for the Playwright "
                        "runner configuration."
                    )
                }
            )
        return result

    @staticmethod
    def _find_project_root(
        repository: Path,
        test_path: Path,
    ) -> Path | None:
        for candidate in (test_path.parent, *test_path.parent.parents):
            if candidate == repository.parent:
                break
            if candidate == repository or repository in candidate.parents:
                if (candidate / "package.json").is_file():
                    return candidate
        return None
