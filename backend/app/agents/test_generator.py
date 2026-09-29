import json

from app.agents.providers import LLMRequest
from app.agents.test_generation import (
    GeneratedTestCase,
    TestGenerationRequest,
    TestGenerationResponse,
)


class TestGenerationAgent:
    """
    Generate structured software test cases using
    repository-aware context.
    """

    SYSTEM_PROMPT = """
You are TestForge's Test Generation Agent.

Your task is to generate precise, repository-aware software
test cases from the supplied user request and repository context.

Follow these rules:

1. Use the repository context as the primary source of truth.
2. Do not invent files, functions, APIs, classes, or behavior
   that are not supported by the supplied repository context.
3. Cover the requested test categories.
4. Include positive, negative, boundary, exception, and edge
   cases when they are relevant.
5. Each test must be independently understandable.
6. Steps must be concrete and executable by a tester.
7. Expected results must be observable and specific.
8. Identify the relevant target file and function whenever
   repository context supports it.
9. Return ONLY valid JSON.
10. Do not wrap the JSON in Markdown code fences.

The JSON structure must be:

{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "...",
      "description": "...",
      "test_type": "functional",
      "priority": "high",
      "preconditions": [],
      "steps": [],
      "expected_result": "...",
      "target_file": "...",
      "target_function": "..."
    }
  ]
}

Allowed test_type values:

functional
integration
api
regression
boundary
negative
exception
edge_case
"""

    def build_prompt(
        self,
        request: TestGenerationRequest,
        context: str,
    ) -> str:
        requested_types = ", ".join(
            test_type.value
            for test_type in request.test_types
        )

        return f"""
Generate {request.count} test cases.

User requirement:
{request.prompt}

Repository:
{request.repository_path}

Requested test categories:
{requested_types}

Repository context:
{context}

Return exactly the JSON structure requested by the
system instructions.
""".strip()

    def parse_response(
        self,
        content: str,
        repository_path: str,
    ) -> TestGenerationResponse:
        cleaned = content.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "LLM returned invalid JSON for test generation."
            ) from exc

        raw_tests = payload.get("test_cases")

        if not isinstance(raw_tests, list):
            raise ValueError(
                "LLM response does not contain a valid "
                "'test_cases' list."
            )

        test_cases = [
            GeneratedTestCase.model_validate(test)
            for test in raw_tests
        ]

        return TestGenerationResponse(
            repository_path=repository_path,
            test_cases=test_cases,
            total_tests=len(test_cases),
        )

    async def generate(
        self,
        request: TestGenerationRequest,
        context: str,
        orchestrator,
    ) -> TestGenerationResponse:
        prompt = self.build_prompt(
            request=request,
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

        return self.parse_response(
            content=response.content,
            repository_path=request.repository_path,
        )