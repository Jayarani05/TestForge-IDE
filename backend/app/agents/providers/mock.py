from app.agents.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
)


class MockLLMProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "testforge-mock"

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        model = request.model or self.default_model

        prompt_lower = request.prompt.lower()

        # ---------------------------------------------------------
        # TEST CODE GENERATION
        # ---------------------------------------------------------
        # This condition MUST come before test-case generation
        # because the test-code prompt also contains "Test cases".
        # ---------------------------------------------------------
        if (
            "generate executable automated tests" in prompt_lower
            or "return only the executable source code" in prompt_lower
        ):
            content = '''
import pytest

from app.repository.analyzer_service import analyze_repository


REPOSITORY_PATH = r"C:\\Users\\jayar\\Downloads\\TestForge IDE"


def test_repository_analysis_completes_successfully():
    """
    TC-001:
    Verify that repository analysis completes successfully.
    """
    result = analyze_repository(REPOSITORY_PATH)

    assert result is not None


def test_invalid_repository_path_is_rejected():
    """
    TC-002:
    Verify that an invalid repository path is rejected.
    """
    invalid_path = r"C:\\invalid\\repository\\path"

    with pytest.raises(Exception):
        analyze_repository(invalid_path)
'''.strip()

        # ---------------------------------------------------------
        # TEST CASE GENERATION
        # ---------------------------------------------------------
        elif (
            "generate" in prompt_lower
            and "test cases" in prompt_lower
        ):
            content = """
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Verify repository analysis",
      "description": "Verify that repository analysis completes successfully.",
      "test_type": "functional",
      "priority": "high",
      "preconditions": [
        "A valid repository path is available"
      ],
      "steps": [
        "Provide the repository path",
        "Start repository analysis",
        "Wait for analysis to complete"
      ],
      "expected_result": "Repository analysis completes successfully.",
      "target_file": "backend/app/repository/analyzer_service.py",
      "target_function": "analyze_repository"
    },
    {
      "id": "TC-002",
      "title": "Handle invalid repository path",
      "description": "Verify that an invalid repository path is rejected.",
      "test_type": "negative",
      "priority": "high",
      "preconditions": [
        "The repository path does not exist"
      ],
      "steps": [
        "Provide an invalid repository path",
        "Start repository analysis"
      ],
      "expected_result": "The API returns an appropriate validation error.",
      "target_file": "backend/app/api/v1/repository.py",
      "target_function": "analyze_repository"
    }
  ]
}
""".strip()

        # ---------------------------------------------------------
        # DEFAULT MOCK RESPONSE
        # ---------------------------------------------------------
        else:
            prompt_preview = request.prompt[:1000]

            content = (
                "Mock LLM received the following prompt:\n\n"
                f"{prompt_preview}"
            )

        return LLMResponse(
            provider=self.provider_name,
            model=model,
            content=content,
        )