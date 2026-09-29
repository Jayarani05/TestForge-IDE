from pathlib import Path
import json
import re

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
        "cargo.toml": "rust",
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

        analysis = RepositoryAnalysis(
            repository_path=str(root),
            project_name=root.name,
            projects=projects,
        )

        analysis.languages = self._detect_languages(
            tree.files
        )

        analysis.frameworks = self._detect_frameworks(
            tree.files
        )

        analysis.dependencies = self._detect_dependencies(
            tree.files
        )

        analysis.configuration_files = (
            self._detect_configuration_files(
                tree.files
            )
        )

        analysis.api_specifications = (
            self._detect_api_specifications(
                tree.files
            )
        )

        analysis.documentation_files = (
            self._detect_documentation_files(
                tree.files
            )
        )

        analysis.test_files = (
            self._detect_test_files(
                tree.files
            )
        )

        analysis.automation_files = (
            self._detect_automation_files(
                tree.files
            )
        )

        if len(projects) == 1:
            analysis.project_type = projects[0].project_type
        elif len(projects) > 1:
            analysis.project_type = "multi-project"
        else:
            analysis.project_type = "unknown"

        return analysis

    def _detect_projects(
        self,
        root: Path,
        files,
    ) -> list[ProjectInfo]:
        projects: dict[str, ProjectInfo] = {}

        for file in files:
            file_name = file.name.lower()

            if file_name not in self.PROJECT_MARKERS:
                continue

            project_type = self.PROJECT_MARKERS[file_name]
            file_path = Path(file.path)

            try:
                relative_parent = file_path.parent.relative_to(root)
            except ValueError:
                continue

            if str(relative_parent) == ".":
                project_path = root
                project_name = root.name
                relative_path = "."
            else:
                project_path = root / relative_parent
                project_name = project_path.name
                relative_path = str(relative_parent)

            key = str(project_path).lower()

            if key not in projects:
                projects[key] = ProjectInfo(
                    name=project_name,
                    path=relative_path,
                    project_type=project_type,
                )

            project = projects[key]

            if file.relative_path not in project.dependency_files:
                project.dependency_files.append(file.relative_path)

            file_language = file.language

            if file_language and file_language not in project.languages:
                project.languages.append(file_language)

            if file_name == "package.json":
                project.frameworks.extend(
                    framework
                    for framework in self._frameworks_from_package_json(
                        file_path
                    )
                    if framework not in project.frameworks
                )

            elif file_name == "requirements.txt":
                project.frameworks.extend(
                    framework
                    for framework in self._frameworks_from_requirements(
                        file_path
                    )
                    if framework not in project.frameworks
                )

            elif file_name == "pom.xml":
                project.frameworks.extend(
                    framework
                    for framework in self._frameworks_from_pom(
                        file_path
                    )
                    if framework not in project.frameworks
                )

        return sorted(
            projects.values(),
            key=lambda project: project.path,
        )

    def _detect_languages(self, files) -> list[str]:
        ignored_types = {
            "Documentation",
            "Docker",
            "Docker Compose",
            "Alembic",
            "Node.js",
            "Maven",
            "Gradle",
        }

        languages = {
            file.language
            for file in files
            if file.language
            and file.language not in ignored_types
        }

        return sorted(languages)

    def _detect_frameworks(self, files) -> list[str]:
        frameworks: set[str] = set()

        for file in files:
            file_name = file.name.lower()
            file_path = Path(file.path)

            if file_name == "package.json":
                frameworks.update(
                    self._frameworks_from_package_json(
                        file_path
                    )
                )

            elif file_name == "requirements.txt":
                frameworks.update(
                    self._frameworks_from_requirements(
                        file_path
                    )
                )

            elif file_name == "pom.xml":
                frameworks.update(
                    self._frameworks_from_pom(
                        file_path
                    )
                )

        return sorted(frameworks)

    def _frameworks_from_package_json(
        self,
        file_path: Path,
    ) -> set[str]:
        frameworks: set[str] = set()

        try:
            data = json.loads(
                file_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return frameworks

        dependencies = {}

        dependencies.update(
            data.get("dependencies", {})
        )

        dependencies.update(
            data.get("devDependencies", {})
        )

        patterns = {
            "react": "React",
            "next": "Next.js",
            "vue": "Vue",
            "angular": "Angular",
            "express": "Express",
            "@nestjs/core": "NestJS",
            "vite": "Vite",
            "playwright": "Playwright",
            "selenium": "Selenium",
            "electron": "Electron",
        }

        for dependency in dependencies:
            dependency_lower = dependency.lower()

            for keyword, framework in patterns.items():
                if (
                    dependency_lower == keyword
                    or keyword in dependency_lower
                ):
                    frameworks.add(framework)

        return frameworks

    def _frameworks_from_requirements(
        self,
        file_path: Path,
    ) -> set[str]:
        frameworks: set[str] = set()

        try:
            content = file_path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).lower()
        except OSError:
            return frameworks

        patterns = {
            "fastapi": "FastAPI",
            "flask": "Flask",
            "django": "Django",
            "pytest": "Pytest",
            "selenium": "Selenium",
            "playwright": "Playwright",
        }

        for keyword, framework in patterns.items():
            if keyword in content:
                frameworks.add(framework)

        return frameworks

    def _frameworks_from_pom(
        self,
        file_path: Path,
    ) -> set[str]:
        frameworks: set[str] = set()

        try:
            content = file_path.read_text(
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
        files,
    ) -> list[DependencyInfo]:
        dependencies: list[DependencyInfo] = []

        for file in files:
            file_name = file.name.lower()

            if file_name == "requirements.txt":
                dependencies.extend(
                    self._parse_requirements(
                        Path(file.path)
                    )
                )

            elif file_name == "package.json":
                dependencies.extend(
                    self._parse_package_json(
                        Path(file.path)
                    )
                )

        return dependencies

    def _parse_requirements(
        self,
        file_path: Path,
    ) -> list[DependencyInfo]:
        dependencies: list[DependencyInfo] = []

        try:
            content = file_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            return dependencies

        for raw_line in content.splitlines():
            line = raw_line.strip()

            # Ignore empty lines and comments.
            if not line or line.startswith("#"):
                continue

            # Ignore pip options and include/constraint directives.
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
                    "--no-index",
                )
            ):
                continue

            # Ignore direct URL / VCS requirements.
            if line.startswith(
                (
                    "http://",
                    "https://",
                    "git+",
                    "svn+",
                    "hg+",
                    "bzr+",
                )
            ):
                continue

            # Remove inline comments.
            line = line.split(" #", 1)[0].strip()

            match = re.match(
                r"^([A-Za-z0-9][A-Za-z0-9_.-]*)"
                r"(?:\s*(===|==|!=|~=|>=|<=|>|<)"
                r"\s*([^\s;,]+))?",
                line,
            )

            if match is None:
                continue

            name = match.group(1).strip()
            version = match.group(3)

            if not name:
                continue

            dependencies.append(
                DependencyInfo(
                    name=name,
                    version=version,
                    source_file=str(file_path),
                )
            )

        return dependencies

    def _parse_package_json(
        self,
        file_path: Path,
    ) -> list[DependencyInfo]:
        dependencies = []

        try:
            data = json.loads(
                file_path.read_text(
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
        ):
            section_data = data.get(
                section,
                {}
            )

            for name, version in section_data.items():
                dependencies.append(
                    DependencyInfo(
                        name=name,
                        version=str(version),
                        source_file=str(file_path),
                    )
                )

        return dependencies

    def _detect_configuration_files(
        self,
        files,
    ) -> list[ConfigurationFileInfo]:
        configurations = []

        configuration_map = {
            ".env": "Environment",
            ".env.example": "Environment",
            "application.properties": "Application Configuration",
            "application.yml": "Application Configuration",
            "application.yaml": "Application Configuration",
            "alembic.ini": "Alembic",
            "docker-compose.yml": "Docker Compose",
            "docker-compose.yaml": "Docker Compose",
            "vite.config.ts": "Vite",
            "vite.config.js": "Vite",
            "tsconfig.json": "TypeScript",
            "eslint.config.js": "ESLint",
        }

        for file in files:
            configuration_type = configuration_map.get(
                file.name.lower()
            )

            if configuration_type:
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
        specifications = []

        api_file_names = {
            "openapi.json": "OpenAPI",
            "openapi.yaml": "OpenAPI",
            "openapi.yml": "OpenAPI",
            "swagger.json": "Swagger",
            "swagger.yaml": "Swagger",
            "swagger.yml": "Swagger",
        }

        for file in files:
            specification_type = api_file_names.get(
                file.name.lower()
            )

            if specification_type:
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
        documentation = []

        documentation_names = {
            "readme": "README",
            "readme.md": "README",
            "readme.txt": "README",
            "contributing.md": "Contributing",
            "changelog.md": "Changelog",
            "architecture.md": "Architecture",
        }

        for file in files:
            documentation_type = documentation_names.get(
                file.name.lower()
            )

            if documentation_type:
                documentation.append(
                    DocumentationFileInfo(
                        path=file.relative_path,
                        documentation_type=documentation_type,
                    )
                )

        return documentation

    def _detect_test_files(
        self,
        files,
    ) -> list[TestFileInfo]:
        test_files = []

        for file in files:
            path = file.relative_path.lower()
            name = file.name.lower()

            if not (
                "test" in name
                or "tests" in path
                or "__tests__" in path
                or "spec" in name
            ):
                continue

            framework = None

            if file.language == "Python":
                framework = "Pytest"
            elif file.language in {
                "JavaScript",
                "TypeScript",
            }:
                framework = "JavaScript Testing"
            elif file.language == "Java":
                framework = "Java Testing"

            test_files.append(
                TestFileInfo(
                    path=file.relative_path,
                    framework=framework,
                    language=file.language,
                )
            )

        return test_files

    def _detect_automation_files(
        self,
        files,
    ) -> list[AutomationFileInfo]:
        automation_files = []

        for file in files:
            path = file.relative_path.lower()

            if "playwright" in path:
                automation_files.append(
                    AutomationFileInfo(
                        path=file.relative_path,
                        automation_type="Playwright",
                    )
                )
            elif "selenium" in path:
                automation_files.append(
                    AutomationFileInfo(
                        path=file.relative_path,
                        automation_type="Selenium",
                    )
                )
            elif "cypress" in path:
                automation_files.append(
                    AutomationFileInfo(
                        path=file.relative_path,
                        automation_type="Cypress",
                    )
                )
            elif "automation" in path:
                automation_files.append(
                    AutomationFileInfo(
                        path=file.relative_path,
                        automation_type="Automation",
                    )
                )

        return automation_files
