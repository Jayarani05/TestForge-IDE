from enum import Enum

from pydantic import BaseModel, Field

from app.agents.test_generation import GeneratedTestCase

class TestCodeFramework(str, Enum):
    PYTEST = "pytest"
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"


class TestCodeLanguage(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


class TestCodeGenerationRequest(BaseModel):
    repository_path: str
    test_cases: list[GeneratedTestCase] = Field(
        default_factory=list
    )
    framework: TestCodeFramework = TestCodeFramework.PYTEST
    language: TestCodeLanguage = TestCodeLanguage.PYTHON
    output_file: str | None = None


class GeneratedTestCode(BaseModel):
    framework: TestCodeFramework
    language: TestCodeLanguage
    file_path: str
    code: str
    test_case_ids: list[str] = Field(
        default_factory=list
    )


class TestCodeGenerationResponse(BaseModel):
    repository_path: str
    generated_files: list[GeneratedTestCode] = Field(
        default_factory=list
    )
    total_files: int = 0