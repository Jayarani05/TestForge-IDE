from app.agents.orchestrator import LLMOrchestrator
from app.agents.providers import LLMRequest
from app.agents.routing import LLMRoutingStrategy
from app.agents.schemas import (
    AgentRequest,
    AgentResponse,
    RepositoryAnalysis,
)
from app.agents.tasks import AgentTask
from app.repository.analyzer_service import (
    RepositoryAnalyzerService,
)


class TestForgeAgent:
    """
    Main AI agent for TestForge testing workflows.
    """

    def __init__(
        self,
        orchestrator: LLMOrchestrator | None = None,
    ) -> None:
        self.orchestrator = (
            orchestrator
            or LLMOrchestrator()
        )

        self.repository_analyzer = (
            RepositoryAnalyzerService()
        )

    async def execute(
        self,
        request: AgentRequest,
    ) -> AgentResponse:
        prompt = self._build_prompt(request)

        llm_request = LLMRequest(
            prompt=prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        route = LLMRoutingStrategy.get_route(
            request.task
        )

        if request.provider != "auto":
            provider = request.provider

            fallback_providers = [
                name
                for name in route
                if name != provider
            ]
        else:
            provider = route[0]
            fallback_providers = route[1:]

        if request.fallback_providers:
            fallback_providers = (
                request.fallback_providers
                + fallback_providers
            )

        response = await self.orchestrator.generate(
            request=llm_request,
            provider_name=provider,
            fallback_providers=fallback_providers,
        )

        analysis = None

        if (
            request.task == AgentTask.ANALYZE_REPOSITORY
            and request.repository_path
        ):
            analysis = self._analyze_repository(
                request.repository_path
            )

        return AgentResponse(
            task=request.task,
            provider=response.provider,
            model=response.model,
            content=response.content,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            analysis=analysis,
        )

    def _analyze_repository(
        self,
        repository_path: str,
    ) -> RepositoryAnalysis:
        """
        Run the deterministic repository analyzer and
        convert its result into the AI response schema.
        """

        result = (
            self.repository_analyzer.analyze_repository(
                repository_path
            )
        )

        technologies = self._unique(
            [
                *result.languages,
                *result.frameworks,
            ]
        )

        dependencies = self._unique(
            [
                (
                    f"{dependency.name}"
                    f"=={dependency.version}"
                    if dependency.version
                    else dependency.name
                )
                for dependency in result.dependencies
            ]
        )

        important_modules = self._unique(
            [
                (
                    f"{project.name} "
                    f"({project.project_type})"
                )
                for project in result.projects
            ]
            + [
                project.path
                for project in result.projects
            ]
        )

        apis = [
            (
                f"{item.path} "
                f"({item.specification_type})"
            )
            for item in result.api_specifications
        ]

        configurations = [
            (
                f"{item.path} "
                f"({item.configuration_type})"
            )
            for item in result.configuration_files
        ]

        existing_tests = [
            (
                f"{item.path}"
                + (
                    f" ({item.framework})"
                    if item.framework
                    else ""
                )
            )
            for item in result.test_files
        ]

        automation_assets = [
            (
                f"{item.path} "
                f"({item.automation_type})"
            )
            for item in result.automation_files
        ]

        testing_areas = (
            self._derive_testing_areas(
                result
            )
        )

        architecture = (
            self._build_architecture(
                result
            )
        )

        return RepositoryAnalysis(
            architecture=architecture,
            technologies=technologies,
            dependencies=dependencies,
            important_modules=important_modules,
            apis=self._unique(apis),
            configurations=self._unique(
                configurations
            ),
            existing_tests=self._unique(
                existing_tests
            ),
            automation_assets=self._unique(
                automation_assets
            ),
            testing_areas=testing_areas,
        )

    @staticmethod
    def _build_architecture(
        result,
    ) -> str:
        if not result.projects:
            return (
                "Repository architecture could not "
                "be determined from detected project markers."
            )

        if len(result.projects) == 1:
            project = result.projects[0]

            technologies = []

            if project.languages:
                technologies.extend(
                    project.languages
                )

            if project.frameworks:
                technologies.extend(
                    project.frameworks
                )

            technology_text = (
                ", ".join(
                    dict.fromkeys(
                        technologies
                    )
                )
                if technologies
                else "detected project technology"
            )

            return (
                f"Single {project.project_type} "
                f"project using {technology_text}."
            )

        project_descriptions = []

        for project in result.projects:
            technology_parts = [
                *project.languages,
                *project.frameworks,
            ]

            technology_text = (
                ", ".join(
                    dict.fromkeys(
                        technology_parts
                    )
                )
                if technology_parts
                else project.project_type
            )

            project_descriptions.append(
                f"{project.name}: "
                f"{project.project_type} "
                f"({technology_text})"
            )

        return (
            "Multi-project repository with "
            + "; ".join(project_descriptions)
            + "."
        )

    @staticmethod
    def _derive_testing_areas(
        result,
    ) -> list[str]:
        areas: list[str] = []

        if result.languages:
            areas.append(
                "Language-specific unit and functional testing"
            )

        if result.frameworks:
            areas.append(
                "Framework-aware integration testing"
            )

        if result.api_specifications:
            areas.append(
                "API contract and endpoint testing"
            )

        if result.test_files:
            areas.append(
                "Regression testing of existing test suites"
            )

        if result.automation_files:
            areas.append(
                "Automation workflow validation"
            )

        if result.configuration_files:
            areas.append(
                "Configuration and environment testing"
            )

        if result.dependencies:
            areas.append(
                "Dependency and integration compatibility testing"
            )

        if not areas:
            areas.append(
                "Repository-wide functional, negative, "
                "boundary, exception, and regression testing"
            )

        return areas

    @staticmethod
    def _unique(
        values: list[str],
    ) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for value in values:
            if not value:
                continue

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
    def _build_prompt(
        request: AgentRequest,
    ) -> str:
        sections: list[str] = []

        sections.append(
            f"TestForge Task: {request.task.value}"
        )

        sections.append(
            f"User Request:\n{request.prompt}"
        )

        if request.repository_path:
            sections.append(
                "Repository:\n"
                f"{request.repository_path}"
            )

        if request.context:
            sections.append(
                "Repository Context:\n"
                f"{request.context}"
            )

        if request.task == AgentTask.EXPLAIN_CODE:
            sections.append(
                "Explain the supplied code based only on its actual source. "
                "Cover its purpose, main logic, functions or classes, "
                "dependencies, and execution flow. Do not modify the code, "
                "do not execute it, and do not expose secrets or credentials."
            )

        sections.append(
            "Provide a precise response suitable "
            "for the TestForge testing workflow."
        )

        return "\n\n".join(sections)