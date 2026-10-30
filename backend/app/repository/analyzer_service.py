import json
from pathlib import Path

from app.repository.analyzer import (
    ApiSpecificationInfo,
    AutomationFileInfo,
    ConfigurationFileInfo,
    DependencyInfo,
    DocumentationFileInfo,
    ProjectInfo,
    RepositoryAnalysis,
    TestFileInfo,
)
from app.repository.tree_service import RepositoryTreeService


class RepositoryAnalyzerService:
    PROJECT_MARKERS = {
        "package.json": "node",
        "requirements.txt": "python",
        "pyproject.toml": "python",
        "pom.xml": "java-maven",
        "build.gradle": "java-gradle",
        "build.gradle.kts": "java-gradle",
        "go.mod": "go",
        "Cargo.toml": "rust",
        "composer.json": "php",
    }

    def __init__(self) -> None:
        self.tree_service = RepositoryTreeService()

    def analyze_repository(
        self,
        repository_path: str,
    ) -> RepositoryAnalysis:
        root = Path(repository_path).expanduser().resolve()

        if not root.exists():
            raise FileNotFoundError(
                "Repository path does not exist."
            )

        if not root.is_dir():
            raise ValueError(
                "Repository path must be a directory."
            )

        tree = self.tree_service.scan_repository(
            str(root)
        )

        projects = self._detect_projects(
            root,
            tree.files,
        )

        languages = self._detect_languages(
            tree.files
        )

        frameworks = self._detect_frameworks(
            root,
            tree.files,
        )

        dependencies = self._detect_dependencies(
            root,
            tree.files,
        )

        configuration_files = (
            self._detect_configuration_files(
                tree.files
            )
        )

        api_specifications = (
            self._detect_api_specifications(
                tree.files
            )
        )

        documentation_files = (
            self._detect_documentation_files(
                tree.files
            )
        )

        test_files = self._detect_test_files(
            tree.files
        )

        automation_files = (
            self._detect_automation_files(
                tree.files
            )
        )

        project_types = {
            project.project_type
            for project in projects
        }

        if len(project_types) == 1:
            project_type = next(iter(project_types))
        elif len(project_types) > 1:
            project_type = "multi-project"
        else:
            project_type = "unknown"

        recommended_test_framework, framework_evidence = (
            self._recommend_test_framework(
                dependencies=dependencies,
                frameworks=frameworks,
                test_files=test_files,
                automation_files=automation_files,
            )
        )
        framework_support_evidence = (
            self._framework_support_evidence(
                dependencies=dependencies,
                frameworks=frameworks,
                test_files=test_files,
                automation_files=automation_files,
            )
        )
        supported_test_languages = self._supported_test_languages(
            languages=languages,
            project_type=project_type,
        )
        compatible_frameworks = {
            framework: evidence
            for framework, evidence in framework_support_evidence.items()
            if self._framework_compatible_with_languages(
                framework,
                supported_test_languages,
            )
        }
        if recommended_test_framework not in compatible_frameworks:
            recommended_test_framework = None
            framework_evidence = []

        return RepositoryAnalysis(
            repository_path=str(root),
            project_name=root.name,
            project_type=project_type,
            projects=projects,
            languages=languages,
            frameworks=frameworks,
            dependencies=dependencies,
            configuration_files=configuration_files,
            api_specifications=api_specifications,
            documentation_files=documentation_files,
            test_files=test_files,
            automation_files=automation_files,
            recommended_test_framework=recommended_test_framework,
            framework_recommendation_evidence=framework_evidence,
            supported_test_frameworks=list(compatible_frameworks),
            framework_support_evidence=compatible_frameworks,
            supported_test_languages=supported_test_languages,
        )

    @staticmethod
    def _framework_support_evidence(
        *,
        dependencies: list[DependencyInfo],
        frameworks: list[str],
        test_files: list[TestFileInfo],
        automation_files: list[AutomationFileInfo],
    ) -> dict[str, list[str]]:
        evidence: dict[str, list[str]] = {}
        supported_dependencies = {
            "pytest": "pytest",
            "playwright": "playwright",
            "@playwright/test": "playwright",
            "selenium": "selenium",
            "selenium-webdriver": "selenium",
        }
        detected_frameworks = {
            "Pytest": "pytest",
            "Playwright": "playwright",
            "Selenium": "selenium",
        }

        for dependency in dependencies:
            framework = supported_dependencies.get(
                dependency.name.lower()
            )
            if framework:
                evidence.setdefault(framework, []).append(
                    f"Declared dependency: {dependency.name}"
                )

        for detected_framework in frameworks:
            framework = detected_frameworks.get(detected_framework)
            if framework:
                evidence.setdefault(framework, []).append(
                    f"Detected configured framework: {detected_framework}"
                )

        for test_file in test_files:
            if test_file.framework == "Pytest":
                evidence.setdefault("pytest", []).append(
                    "Existing test file: "
                    + test_file.path.replace("\\", "/")
                )

        for automation_file in automation_files:
            framework = {
                "Playwright": "playwright",
                "Selenium": "selenium",
            }.get(automation_file.automation_type)
            if framework:
                evidence.setdefault(framework, []).append(
                    "Existing automation file: "
                    + automation_file.path.replace("\\", "/")
                )

        return evidence

    @staticmethod
    def _supported_test_languages(
        *,
        languages: list[str],
        project_type: str,
    ) -> list[str]:
        supported = {
            "Python",
            "JavaScript",
            "TypeScript",
        }
        detected = [language for language in languages if language in supported]

        if not detected and project_type == "python":
            detected.append("Python")
        elif not detected and project_type == "node":
            detected.append("JavaScript")

        return detected

    @staticmethod
    def _framework_compatible_with_languages(
        framework: str,
        languages: list[str],
    ) -> bool:
        compatible_languages = {
            "pytest": {"Python"},
            "playwright": {"Python", "JavaScript", "TypeScript"},
            "selenium": {"Python", "JavaScript", "TypeScript"},
        }
        return bool(
            compatible_languages.get(framework, set()).intersection(languages)
        )

    @staticmethod
    def _recommend_test_framework(
        *,
        dependencies: list[DependencyInfo],
        frameworks: list[str],
        test_files: list[TestFileInfo],
        automation_files: list[AutomationFileInfo],
    ) -> tuple[str | None, list[str]]:
        configured: dict[str, list[str]] = {}
        existing_tests: dict[str, list[str]] = {}

        supported_dependencies = {
            "pytest": "pytest",
            "playwright": "playwright",
            "@playwright/test": "playwright",
            "selenium": "selenium",
            "selenium-webdriver": "selenium",
        }

        for dependency in dependencies:
            framework = supported_dependencies.get(
                dependency.name.lower()
            )
            if framework:
                configured.setdefault(framework, []).append(
                    f"Declared dependency: {dependency.name}"
                )

        detected_frameworks = {
            "Pytest": "pytest",
            "Playwright": "playwright",
            "Selenium": "selenium",
        }
        for detected_framework in frameworks:
            framework = detected_frameworks.get(detected_framework)
            if framework and framework not in configured:
                configured.setdefault(framework, []).append(
                    f"Detected configured framework: {detected_framework}"
                )

        for test_file in test_files:
            if test_file.framework == "Pytest":
                existing_tests.setdefault("pytest", []).append(
                    "Existing test file: "
                    + test_file.path.replace("\\", "/")
                )

        automation_frameworks = {
            "Playwright": "playwright",
            "Selenium": "selenium",
        }
        for automation_file in automation_files:
            framework = automation_frameworks.get(
                automation_file.automation_type
            )
            if framework:
                existing_tests.setdefault(framework, []).append(
                    "Existing automation file: "
                    + automation_file.path.replace("\\", "/")
                )

        if len(existing_tests) == 1:
            framework, evidence = next(iter(existing_tests.items()))
            return framework, evidence

        if len(existing_tests) > 1:
            return None, []

        if len(configured) == 1:
            framework, evidence = next(iter(configured.items()))
            return framework, evidence

        return None, []

    def _detect_projects(
        self,
        root: Path,
        files,
    ) -> list[ProjectInfo]:
        projects: dict[str, ProjectInfo] = {}

        for file in files:
            marker_type = self.PROJECT_MARKERS.get(
                file.name
            )

            if marker_type is None:
                continue

            file_path = Path(file.path)

            try:
                project_path = file_path.parent.relative_to(root)
            except ValueError:
                continue

            if str(project_path) == ".":
                project_name = root.name
                project_relative_path = "."
            else:
                project_name = project_path.name
                project_relative_path = str(
                    project_path
                )

            key = str(project_path)

            if key not in projects:
                projects[key] = ProjectInfo(
                    name=project_name,
                    path=project_relative_path,
                    project_type=marker_type,
                    languages=[],
                    frameworks=[],
                    dependency_files=[],
                )

            projects[key].dependency_files.append(
                str(
                    Path(file.relative_path)
                )
            )

        return list(projects.values())

    def _detect_languages(
        self,
        files,
    ) -> list[str]:
        languages: set[str] = set()

        for file in files:
            if file.language is not None:
                if file.language in {
                    "Python",
                    "Java",
                    "JavaScript",
                    "TypeScript",
                    "C",
                    "C++",
                    "C#",
                    "Go",
                    "Rust",
                    "PHP",
                    "Ruby",
                    "Kotlin",
                    "Swift",
                    "HTML",
                    "CSS",
                    "SCSS",
                    "SQL",
                    "Shell",
                    "Batch",
                    "PowerShell",
                    "JSON",
                    "XML",
                    "YAML",
                    "Markdown",
                }:
                    languages.add(file.language)

        return sorted(languages)

    def _detect_frameworks(
        self,
        root: Path,
        files,
    ) -> list[str]:
        frameworks: set[str] = set()

        for file in files:
            file_path = Path(file.path)

            if file.name == "package.json":
                frameworks.update(
                    self._detect_node_frameworks(
                        file_path
                    )
                )

            elif file.name == "requirements.txt":
                frameworks.update(
                    self._detect_python_frameworks(
                        file_path
                    )
                )

            elif file.name == "pyproject.toml":
                frameworks.update(
                    self._detect_python_frameworks(
                        file_path
                    )
                )

            elif file.name == "pom.xml":
                frameworks.update(
                    self._detect_java_frameworks(
                        file_path
                    )
                )

        return sorted(frameworks)

    def _detect_node_frameworks(
        self,
        path: Path,
    ) -> set[str]:
        frameworks: set[str] = set()

        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return frameworks

        dependencies: dict[str, object] = {}

        dependencies.update(
            data.get("dependencies", {})
        )

        dependencies.update(
            data.get("devDependencies", {})
        )

        dependency_names = set(
            dependencies.keys()
        )

        if "react" in dependency_names:
            frameworks.add("React")

        if "next" in dependency_names:
            frameworks.add("Next.js")

        if "vue" in dependency_names:
            frameworks.add("Vue")

        if "@angular/core" in dependency_names:
            frameworks.add("Angular")

        if "express" in dependency_names:
            frameworks.add("Express")

        if "@nestjs/core" in dependency_names:
            frameworks.add("NestJS")

        if "vite" in dependency_names:
            frameworks.add("Vite")

        if "@playwright/test" in dependency_names:
            frameworks.add("Playwright")

        if "selenium-webdriver" in dependency_names:
            frameworks.add("Selenium")

        if "electron" in dependency_names:
            frameworks.add("Electron")

        return frameworks

    def _detect_python_frameworks(
        self,
        path: Path,
    ) -> set[str]:
        frameworks: set[str] = set()

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).lower()
        except OSError:
            return frameworks

        if "fastapi" in content:
            frameworks.add("FastAPI")

        if "flask" in content:
            frameworks.add("Flask")

        if "django" in content:
            frameworks.add("Django")

        if "pytest" in content:
            frameworks.add("Pytest")

        if "selenium" in content:
            frameworks.add("Selenium")

        if "playwright" in content:
            frameworks.add("Playwright")

        return frameworks

    def _detect_java_frameworks(
        self,
        path: Path,
    ) -> set[str]:
        frameworks: set[str] = set()

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).lower()
        except OSError:
            return frameworks

        if "spring-boot" in content:
            frameworks.add("Spring Boot")

        if "selenium" in content:
            frameworks.add("Selenium")

        if "playwright" in content:
            frameworks.add("Playwright")

        return frameworks

    def _detect_dependencies(
        self,
        root: Path,
        files,
    ) -> list[DependencyInfo]:
        dependencies: list[DependencyInfo] = []

        for file in files:
            path = Path(file.path)

            if file.name == "requirements.txt":
                parsed = self._parse_requirements(
                    path
                )

                for name, version in parsed:
                    dependencies.append(
                        DependencyInfo(
                            name=name,
                            version=version,
                            source_file=str(path),
                        )
                    )

            elif file.name == "package.json":
                parsed = self._parse_package_json(
                    path
                )

                for name, version in parsed:
                    dependencies.append(
                        DependencyInfo(
                            name=name,
                            version=version,
                            source_file=str(path),
                        )
                    )

        return dependencies

    def _parse_requirements(
        self,
        path: Path,
    ) -> list[tuple[str, str | None]]:
        dependencies: list[
            tuple[str, str | None]
        ] = []

        try:
            lines = path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).splitlines()
        except OSError:
            return dependencies

        for line in lines:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if line.startswith(
                (
                    "-r ",
                    "--requirement ",
                    "-c ",
                    "--constraint ",
                    "--index-url ",
                    "--extra-index-url ",
                    "--find-links ",
                    "--trusted-host ",
                )
            ):
                continue

            if line.startswith(
                (
                    "http://",
                    "https://",
                    "git+",
                )
            ):
                continue

            dependency_name = line
            dependency_version: str | None = None

            for operator in (
                "===",
                "==",
                ">=",
                "<=",
                "~=",
                "!=",
                ">",
                "<",
            ):
                if operator in line:
                    (
                        dependency_name,
                        dependency_version,
                    ) = line.split(
                        operator,
                        1,
                    )

                    dependency_name = (
                        dependency_name.strip()
                    )

                    dependency_version = (
                        dependency_version.strip()
                    )

                    break

            dependency_name = (
                dependency_name.strip()
            )

            if not dependency_name:
                continue

            if dependency_name.startswith(
                (
                    "-",
                    "#",
                )
            ):
                continue

            dependencies.append(
                (
                    dependency_name,
                    dependency_version,
                )
            )

        return dependencies

    def _parse_package_json(
        self,
        path: Path,
    ) -> list[tuple[str, str | None]]:
        dependencies: list[
            tuple[str, str | None]
        ] = []

        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return dependencies

        for section in (
            "dependencies",
            "devDependencies",
            "peerDependencies",
            "optionalDependencies",
        ):
            section_dependencies = data.get(
                section,
                {},
            )

            if not isinstance(
                section_dependencies,
                dict,
            ):
                continue

            for name, version in (
                section_dependencies.items()
            ):
                dependencies.append(
                    (
                        str(name),
                        str(version)
                        if version is not None
                        else None,
                    )
                )

        return dependencies

    def _detect_configuration_files(
        self,
        files,
    ) -> list[ConfigurationFileInfo]:
        configurations: list[
            ConfigurationFileInfo
        ] = []

        configuration_map = {
            ".env": "Environment",
            ".env.example": "Environment",
            ".env.local": "Environment",
            ".env.development": "Environment",
            ".env.production": "Environment",
            "alembic.ini": "Alembic",
            "eslint.config.js": "ESLint",
            ".eslintrc": "ESLint",
            ".eslintrc.json": "ESLint",
            ".eslintrc.js": "ESLint",
            "tsconfig.json": "TypeScript",
            "vite.config.ts": "Vite",
            "vite.config.js": "Vite",
            "webpack.config.js": "Webpack",
            "babel.config.js": "Babel",
            "pytest.ini": "Pytest",
            "tox.ini": "Tox",
            "docker-compose.yml": "Docker Compose",
            "docker-compose.yaml": "Docker Compose",
            "Dockerfile": "Docker",
        }

        for file in files:
            configuration_type = (
                configuration_map.get(
                    file.name
                )
            )

            if configuration_type is None:
                continue

            configurations.append(
                ConfigurationFileInfo(
                    path=file.relative_path,
                    configuration_type=configuration_type,
                )
            )

        return configurations

    def _detect_api_specifications(
        self,
        files,
    ) -> list[ApiSpecificationInfo]:
        specifications: list[
            ApiSpecificationInfo
        ] = []

        api_specification_map = {
            "openapi.yaml": "OpenAPI",
            "openapi.yml": "OpenAPI",
            "openapi.json": "OpenAPI",
            "swagger.yaml": "Swagger",
            "swagger.yml": "Swagger",
            "swagger.json": "Swagger",
        }

        for file in files:
            specification_type = (
                api_specification_map.get(
                    file.name
                )
            )

            if specification_type is None:
                continue

            specifications.append(
                ApiSpecificationInfo(
                    path=file.relative_path,
                    specification_type=specification_type,
                )
            )

        return specifications

    def _detect_documentation_files(
        self,
        files,
    ) -> list[DocumentationFileInfo]:
        documentation: list[
            DocumentationFileInfo
        ] = []

        for file in files:
            if file.name.lower() in {
                "readme",
                "readme.md",
                "readme.txt",
                "readme.rst",
            }:
                documentation.append(
                    DocumentationFileInfo(
                        path=file.relative_path,
                        documentation_type="README",
                    )
                )

            elif file.extension == ".md":
                documentation.append(
                    DocumentationFileInfo(
                        path=file.relative_path,
                        documentation_type="Markdown",
                    )
                )

            elif file.extension == ".rst":
                documentation.append(
                    DocumentationFileInfo(
                        path=file.relative_path,
                        documentation_type="reStructuredText",
                    )
                )

        return documentation

    def _detect_test_files(
        self,
        files,
    ) -> list[TestFileInfo]:
        tests: list[TestFileInfo] = []

        for file in files:
            lower_path = file.relative_path.lower()
            lower_name = file.name.lower()

            is_test = (
                lower_name.startswith("test_")
                or lower_name.endswith(
                    "_test.py"
                )
                or ".test." in lower_name
                or ".spec." in lower_name
                or "\\tests\\" in lower_path
                or "/tests/" in lower_path
                or "\\test\\" in lower_path
                or "/test/" in lower_path
            )

            if not is_test:
                continue

            framework: str | None = None

            if file.language == "Python":
                framework = "Pytest"

            elif file.language in {
                "JavaScript",
                "TypeScript",
            }:
                framework = "JavaScript Test"

            elif file.language == "Java":
                framework = "JUnit"

            tests.append(
                TestFileInfo(
                    path=file.relative_path,
                    framework=framework,
                    language=file.language,
                )
            )

        return tests

    def _detect_automation_files(
        self,
        files,
    ) -> list[AutomationFileInfo]:
        automation: list[
            AutomationFileInfo
        ] = []

        for file in files:
            lower_name = file.name.lower()
            lower_path = file.relative_path.lower()

            if any(
                keyword in lower_name
                for keyword in (
                    "playwright",
                    "selenium",
                    "webdriver",
                )
            ):
                automation.append(
                    AutomationFileInfo(
                        path=file.relative_path,
                        automation_type=self._detect_automation_type(
                            lower_name
                        ),
                    )
                )
                continue

            if any(
                keyword in lower_path
                for keyword in (
                    "\\e2e\\",
                    "/e2e/",
                    "\\automation\\",
                    "/automation/",
                )
            ):
                automation.append(
                    AutomationFileInfo(
                        path=file.relative_path,
                        automation_type="End-to-End",
                    )
                )

        return automation

    def _detect_automation_type(
        self,
        file_name: str,
    ) -> str:
        if "playwright" in file_name:
            return "Playwright"

        if "selenium" in file_name:
            return "Selenium"

        if "webdriver" in file_name:
            return "WebDriver"

        return "Automation"