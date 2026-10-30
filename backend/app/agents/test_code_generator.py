from app.agents.code_validator import (
    GeneratedCodeValidationError,
    GeneratedCodeValidator,
)
from app.agents.providers import LLMRequest
from app.agents.test_code_generation import (
    GeneratedTestCode,
    TestCodeGenerationRequest,
    TestCodeGenerationResponse,
)
from app.agents.test_generation import GeneratedTestCase


class TestCodeGenerator:
    SYSTEM_PROMPT = """
You are TestForge's Test Code Generation Agent.

Convert the supplied structured test cases into executable
automated test code.

Rules:

1. Follow the requested testing framework.
2. Follow the requested programming language.
3. Preserve the intent of every supplied test case.
4. Do not invent repository APIs, functions, selectors,
   classes, or behavior that are not supported by the
   supplied repository context.
5. Produce maintainable test code.
6. Include clear test names.
7. Include assertions where the expected result supports them.
8. Include setup only when required.
9. Return ONLY the requested code.
10. Do not wrap the response in Markdown code fences.
11. Use recognizable test structure for the requested framework.
12. If repository context is absent, do not invent repository APIs,
    fixtures, selectors, or expected behavior.
""".strip()

    def __init__(
        self,
        validator: GeneratedCodeValidator | None = None,
    ) -> None:
        self.validator = validator or GeneratedCodeValidator()

    def build_prompt(
        self,
        request: TestCodeGenerationRequest,
        test_cases: list[GeneratedTestCase],
        context: str,
    ) -> str:
        serialized_test_cases = "\n\n".join(
            test_case.model_dump_json(indent=2)
            for test_case in test_cases
        )

        output_file = (
            request.output_file
            or "tests/test_generated.py"
        )

        return f"""
Generate executable automated tests.

Repository:
{request.repository_path}

Framework:
{request.framework.value}

Language:
{request.language.value}

Requested output file:
{output_file}

Test cases:
{serialized_test_cases}

Repository context:
{context}

When repository context is empty, write only framework-valid tests that
derive directly from the supplied scenario steps and expected results.
Do not fabricate application-specific setup or assertions.

Return only the executable source code.
""".strip()

    async def generate(
        self,
        request: TestCodeGenerationRequest,
        test_cases: list[GeneratedTestCase],
        context: str,
        orchestrator,
    ) -> TestCodeGenerationResponse:
        prompt = self.build_prompt(
            request=request,
            test_cases=test_cases,
            context=context,
        )

        llm_request = LLMRequest(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=8192,
        )

        response = await orchestrator.generate(
            request=llm_request,
            provider_name="auto",
            fallback_providers=[],
        )

        code = response.content.strip()

        validation = self.validator.validate(
            code=code,
            language=request.language.value,
            framework=request.framework.value,
        )

        if not validation.valid:
            location = ""

            if validation.line is not None:
                location = (
                    f" at line {validation.line}"
                )

                if validation.column is not None:
                    location += (
                        f", column {validation.column}"
                    )

            raise GeneratedCodeValidationError(
                "Generated code validation failed"
                f"{location}: {validation.error}"
            )

        file_path = (
            request.output_file
            or "tests/test_generated.py"
        )

        generated_file = GeneratedTestCode(
            framework=request.framework,
            language=request.language,
            file_path=file_path,
            code=code,
            test_case_ids=[
                test_case.id
                for test_case in test_cases
            ],
        )

        return TestCodeGenerationResponse(
            repository_path=request.repository_path,
            generated_files=[generated_file],
            total_files=1,
            context_available=bool(context.strip()),
            context_warning=(
                None
                if context.strip()
                else (
                    "No repository context was retrieved. Generated code "
                    "was limited to the supplied scenarios and may need "
                    "repository-specific adaptation."
                )
            ),
        )