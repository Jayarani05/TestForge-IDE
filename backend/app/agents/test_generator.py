import json
import re

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
4. Include additional test types only when they are requested.
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

    INTEGRATION_INSTRUCTIONS = """
For integration scenarios, focus on interactions between
components that are explicitly evidenced by the repository
context. Describe the participating components, the data or
control flow across their boundary, and observable behavior
when the interaction succeeds. Include concrete setup and
steps, and do not assume unavailable services, APIs, schemas,
or dependencies.
"""

    API_INSTRUCTIONS = """
For API scenarios, identify endpoints and HTTP methods only
when they are explicitly evidenced by the repository context.
Describe observable API behavior using supported request
inputs and response contracts. Include status codes,
authentication, authorization, and validation details only
when the context documents them. Focus on the API rather than
UI behavior. If no API endpoint or API specification can be
identified in the context, return an empty test_cases list.
Do not invent paths, methods, parameters, payloads, response
schemas, or undocumented behavior.
"""

    REGRESSION_INSTRUCTIONS = """
For regression scenarios, identify existing behavior from the
supplied source code, tests, or documented contracts and focus
on verifying that behavior continues to work after changes.
Explain which evidenced behavior is being protected and give
reproducible steps with observable expected results.
This workflow may provide only current repository context, not
Git history, prior test results, or before-and-after code.
Unless that information is explicitly supplied, do not claim a
specific change, prior behavior, bug fix, test failure, or
regression risk. Ground scenarios in current evidence and do
not invent functionality or history. If the context contains
no repository evidence, return an empty test_cases list.
"""

    BOUNDARY_INSTRUCTIONS = """
For boundary scenarios, identify explicit constraints in the
supplied repository context, such as minimums, maximums,
ranges, thresholds, string or collection sizes, pagination
limits, and date or time restrictions. Use only documented
constraint values and expected behavior. Where applicable,
cover values below, at, and above each boundary, and explain
the behavior being verified with reproducible steps and
observable results. Do not invent limits, validation rules,
or outcomes, and do not produce generic functional, negative,
exception, or edge-case scenarios. If no boundary constraint
is evidenced in the context, return an empty test_cases list.
"""

    BOUNDARY_CONSTRAINT_PATTERN = re.compile(
        r"(?i)\b(?:"
        r"ge|gt|le|lt|min|max|min_length|max_length|"
        r"min_items|max_items|min_value|max_value|"
        r"minimum|maximum|exclusiveMinimum|exclusiveMaximum|"
        r"minLength|maxLength|minItems|maxItems"
        r")\s*(?:=|:)\s*[\"']?-?\d+"
        r"|(?:>=|<=|>|<)\s*-?\d+"
    )

    NEGATIVE_INSTRUCTIONS = """
For negative scenarios, identify explicit validation,
rejection, authorization, or error behavior in the supplied
repository context. Use invalid or disallowed inputs only
when the relevant rule is evidenced. Verify the rejected
operation and its documented observable response; describe
the invalid condition and provide reproducible steps. Include
authentication, authorization, status codes, or error details
only when supported by the context. Do not invent credentials,
constraints, status codes, or error messages, and do not
produce generic functional, boundary, exception, or edge-case
scenarios. If no negative-test evidence is present, return an
empty test_cases list.
"""

    NEGATIVE_EVIDENCE_PATTERN = re.compile(
        r"(?i)"
        r"\b(?:"
        r"raise\s+(?:(?:\w+\.)?)(?:ValueError|TypeError|"
        r"HTTPException|ValidationError|PermissionError|"
        r"AuthenticationError|AuthorizationError)"
        r"|HTTPException\s*\("
        r"|status_code\s*=\s*4\d\d\b"
        r"|(?:min_length|max_length|min_items|max_items|"
        r"min_value|max_value|ge|gt|le|lt)\s*=\s*-?\d+"
        r"|(?:field_validator|validator)\s*\("
        r"|(?:invalid|unauthorized|forbidden|rejected|"
        r"reject(?:ed|ion)?)\b"
        r")"
    )

    EXCEPTION_INSTRUCTIONS = """
For exception scenarios, identify exception types, raising or
catching behavior, exception propagation, cleanup, and failure
paths explicitly evidenced in repository code or tests. Verify
the documented behavior when that exception path occurs, with
reproducible steps and observable expected results. Keep these
scenarios focused on exception handling and distinct from
invalid-input rejection, boundary values, and unusual but
otherwise supported edge conditions. Do not invent exception
classes, messages, or outcomes. If no exception-handling
evidence is present, return an empty test_cases list.
"""

    EXCEPTION_EVIDENCE_PATTERN = re.compile(
        r"(?i)\b(?:"
        r"raise\s+(?:[\w.]*?(?:Error|Exception))"
        r"|except(?:\s+[\w., ]+)?\s*:"
        r"|try\s*:"
        r"|finally\s*:"
        r"|pytest\.raises\s*\("
        r"|assertRaises\s*\("
        r"|throw\s+(?:new\s+)?[\w.]*?(?:Error|Exception)\b"
        r"|catch\s*\("
        r")"
    )

    EDGE_CASE_INSTRUCTIONS = """
For edge-case scenarios, focus on unusual combinations,
optional states, fallbacks, or conditional interactions
explicitly evidenced in repository code, tests, or
documentation. Explain the unusual condition and verify the
observable behavior with reproducible steps. Keep these
distinct from documented limit boundaries, invalid or
rejected inputs, and exception-handling paths. Do not produce
generic edge-case lists or invent behavior. If no relevant
conditional or optional-state evidence is present, return an
empty test_cases list.
"""

    EDGE_CASE_EVIDENCE_PATTERN = re.compile(
        r"(?i)(?:"
        r"\bis\s+not\s+none\b"
        r"|\bis\s+none\b"
        r"|\bif\s+not\s+"
        r"|\boptional\s*\["
        r"|\bdefault_factory\s*="
        r"|\b(?:fallback|retry|fallback_provider)\b"
        r"|\bif\b[^\r\n]{0,160}\b(?:and|or)\b"
        r")"
    )

    API_ROUTE_PATTERN = re.compile(
        r"(?im)^\s*(?:"
        r"@\w+\.(?:get|post|put|patch|delete|options|head)\s*\("
        r"|(?:app|router|server)\."
        r"(?:get|post|put|patch|delete|options|head)\s*\("
        r")"
    )
    API_SPEC_ENDPOINT_PATTERN = re.compile(
        r"(?im)^\s*[\"']?/[^\s\"'{}:]+"
        r"(?:\{[^}]+\}[^\s\"'{}:]*)?[\"']?\s*:\s*"
        r"(?:\r?\n\s+[\"']?(?:get|post|put|patch|delete|options|head)\s*:"
        r"|\{\s*[\"']?(?:get|post|put|patch|delete|options|head)\s*:)"
    )

    def build_prompt(
        self,
        request: TestGenerationRequest,
        context: str,
    ) -> str:
        requested_types = ", ".join(
            test_type.value
            for test_type in request.test_types
        )
        integration_instructions = (
            self.INTEGRATION_INSTRUCTIONS
            if any(
                test_type.value == "integration"
                for test_type in request.test_types
            )
            else ""
        )
        api_instructions = (
            self.API_INSTRUCTIONS
            if any(
                test_type.value == "api"
                for test_type in request.test_types
            )
            else ""
        )
        regression_instructions = (
            self.REGRESSION_INSTRUCTIONS
            if any(
                test_type.value == "regression"
                for test_type in request.test_types
            )
            else ""
        )
        boundary_instructions = (
            self.BOUNDARY_INSTRUCTIONS
            if any(
                test_type.value == "boundary"
                for test_type in request.test_types
            )
            else ""
        )
        negative_instructions = (
            self.NEGATIVE_INSTRUCTIONS
            if any(
                test_type.value == "negative"
                for test_type in request.test_types
            )
            else ""
        )
        exception_instructions = (
            self.EXCEPTION_INSTRUCTIONS
            if any(
                test_type.value == "exception"
                for test_type in request.test_types
            )
            else ""
        )
        edge_case_instructions = (
            self.EDGE_CASE_INSTRUCTIONS
            if any(
                test_type.value == "edge_case"
                for test_type in request.test_types
            )
            else ""
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

Integration scenario instructions:
{integration_instructions}

API scenario instructions:
{api_instructions}

Regression scenario instructions:
{regression_instructions}

Boundary scenario instructions:
{boundary_instructions}

Negative scenario instructions:
{negative_instructions}

Exception scenario instructions:
{exception_instructions}

Edge-case scenario instructions:
{edge_case_instructions}

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
        requested_types = {
            test_type.value
            for test_type in request.test_types
        }
        api_only = requested_types == {"api"}
        regression_only = requested_types == {"regression"}
        boundary_only = requested_types == {"boundary"}
        negative_only = requested_types == {"negative"}
        exception_only = requested_types == {"exception"}
        edge_case_only = requested_types == {"edge_case"}
        has_api_evidence = (
            self.API_ROUTE_PATTERN.search(context)
            or self.API_SPEC_ENDPOINT_PATTERN.search(context)
        )
        if api_only and not has_api_evidence:
            return TestGenerationResponse(
                repository_path=request.repository_path,
                test_cases=[],
                total_tests=0,
            )
        if regression_only and not context.strip():
            return TestGenerationResponse(
                repository_path=request.repository_path,
                test_cases=[],
                total_tests=0,
            )
        if (
            boundary_only
            and not self.BOUNDARY_CONSTRAINT_PATTERN.search(context)
        ):
            return TestGenerationResponse(
                repository_path=request.repository_path,
                test_cases=[],
                total_tests=0,
            )
        if (
            negative_only
            and not self.NEGATIVE_EVIDENCE_PATTERN.search(context)
        ):
            return TestGenerationResponse(
                repository_path=request.repository_path,
                test_cases=[],
                total_tests=0,
            )
        if (
            exception_only
            and not self.EXCEPTION_EVIDENCE_PATTERN.search(context)
        ):
            return TestGenerationResponse(
                repository_path=request.repository_path,
                test_cases=[],
                total_tests=0,
            )
        if (
            edge_case_only
            and not self.EDGE_CASE_EVIDENCE_PATTERN.search(context)
        ):
            return TestGenerationResponse(
                repository_path=request.repository_path,
                test_cases=[],
                total_tests=0,
            )

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

        parsed_response = self.parse_response(
            content=response.content,
            repository_path=request.repository_path,
        )
        requested_cases = [
            test_case
            for test_case in parsed_response.test_cases
            if test_case.test_type.value in requested_types
        ][
            : request.count
        ]

        return parsed_response.model_copy(
            update={
                "test_cases": requested_cases,
                "total_tests": len(requested_cases),
            }
        )
