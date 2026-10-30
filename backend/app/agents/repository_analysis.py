from pydantic import BaseModel, Field


class RepositoryAnalysisResult(BaseModel):
    architecture: str = ""
    technologies: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    important_modules: list[str] = Field(default_factory=list)
    apis: list[str] = Field(default_factory=list)
    configurations: list[str] = Field(default_factory=list)
    existing_tests: list[str] = Field(default_factory=list)
    automation_assets: list[str] = Field(default_factory=list)
    testing_areas: list[str] = Field(default_factory=list)


class RepositoryAnalysisAgent:
    """
    Converts repository metadata and repository-aware context into a
    structured analysis suitable for the TestForge Insights panel.
    """

    def analyze(
        self,
        repository_summary: dict,
        context: str = "",
    ) -> RepositoryAnalysisResult:
        technologies: list[str] = []
        dependencies: list[str] = []
        important_modules: list[str] = []
        apis: list[str] = []
        configurations: list[str] = []
        existing_tests: list[str] = []
        automation_assets: list[str] = []
        testing_areas: list[str] = []

        for item in repository_summary.get("languages", []):
            if isinstance(item, str):
                technologies.append(item)

        for item in repository_summary.get("frameworks", []):
            if isinstance(item, str):
                technologies.append(item)

        for item in repository_summary.get("dependencies", []):
            if isinstance(item, str):
                dependencies.append(item)

        for item in repository_summary.get("configurations", []):
            if isinstance(item, str):
                configurations.append(item)

        for item in repository_summary.get("api_specs", []):
            if isinstance(item, str):
                apis.append(item)

        for item in repository_summary.get("tests", []):
            if isinstance(item, str):
                existing_tests.append(item)

        for item in repository_summary.get("automation", []):
            if isinstance(item, str):
                automation_assets.append(item)

        for item in repository_summary.get("modules", []):
            if isinstance(item, str):
                important_modules.append(item)

        if not important_modules and context:
            for line in context.splitlines():
                line = line.strip()

                if line.startswith("File:"):
                    file_path = line.replace("File:", "", 1).strip()

                    if file_path:
                        important_modules.append(file_path)

        if not apis:
            api_count = repository_summary.get("api_specifications", 0)

            if isinstance(api_count, int) and api_count > 0:
                apis.append(
                    f"{api_count} API specification(s) detected"
                )

        if not existing_tests:
            test_count = repository_summary.get("test_files", 0)

            if isinstance(test_count, int) and test_count > 0:
                existing_tests.append(
                    f"{test_count} existing test file(s) detected"
                )

        if not automation_assets:
            automation_count = repository_summary.get(
                "automation_files",
                0,
            )

            if isinstance(automation_count, int) and automation_count > 0:
                automation_assets.append(
                    f"{automation_count} automation asset(s) detected"
                )

        testing_areas.extend(
            [
                "Functional testing",
                "Integration testing",
                "Regression testing",
                "Boundary and negative testing",
                "Exception handling",
            ]
        )

        architecture = self._build_architecture_description(
            repository_summary,
        )

        return RepositoryAnalysisResult(
            architecture=architecture,
            technologies=self._unique(technologies),
            dependencies=self._unique(dependencies),
            important_modules=self._unique(important_modules),
            apis=self._unique(apis),
            configurations=self._unique(configurations),
            existing_tests=self._unique(existing_tests),
            automation_assets=self._unique(automation_assets),
            testing_areas=self._unique(testing_areas),
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for value in values:
            normalized = value.strip()

            if not normalized:
                continue

            key = normalized.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(normalized)

        return result

    @staticmethod
    def _build_architecture_description(
        summary: dict,
    ) -> str:
        projects = summary.get("projects", [])

        if projects:
            names = []

            for project in projects:
                if isinstance(project, dict):
                    name = project.get("name")

                    if name:
                        names.append(str(name))

            if names:
                return (
                    "Repository contains the following detected "
                    f"project components: {', '.join(names)}."
                )

        languages = summary.get("languages", [])

        if languages:
            return (
                "Repository architecture is inferred from the detected "
                f"technologies and source files: {', '.join(languages)}."
            )

        return "Repository architecture could not be determined from the available analysis."