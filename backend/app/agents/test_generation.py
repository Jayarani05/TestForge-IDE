from enum import Enum

from pydantic import BaseModel, Field


class TestType(str, Enum):
    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    API = "api"
    REGRESSION = "regression"
    BOUNDARY = "boundary"
    NEGATIVE = "negative"
    EXCEPTION = "exception"
    EDGE_CASE = "edge_case"


class GeneratedTestCase(BaseModel):
    id: str
    title: str
    description: str
    test_type: TestType
    priority: str = "medium"
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    expected_result: str
    target_file: str | None = None
    target_function: str | None = None


class TestGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    repository_path: str
    test_types: list[TestType] = Field(
        default_factory=lambda: [
            TestType.FUNCTIONAL,
            TestType.INTEGRATION,
            TestType.API,
            TestType.REGRESSION,
            TestType.BOUNDARY,
            TestType.NEGATIVE,
            TestType.EXCEPTION,
            TestType.EDGE_CASE,
        ]
    )
    count: int = Field(default=10, ge=1, le=50)


class TestGenerationResponse(BaseModel):
    repository_path: str
    test_cases: list[GeneratedTestCase] = Field(
        default_factory=list
    )
    total_tests: int = 0