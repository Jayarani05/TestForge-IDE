from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

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
    repository_path: str = Field(..., min_length=1)
    test_cases: list[GeneratedTestCase] = Field(
        ..., min_length=1
    )
    framework: TestCodeFramework = TestCodeFramework.PYTEST
    language: TestCodeLanguage = TestCodeLanguage.PYTHON
    output_file: str | None = None

    @model_validator(mode="after")
    def validate_request_content(self):
        for test_case in self.test_cases:
            if not all(
                value.strip()
                for value in (
                    test_case.id,
                    test_case.title,
                    test_case.description,
                    test_case.expected_result,
                )
            ):
                raise ValueError(
                    "Test scenarios must include an id, title, description, "
                    "and expected result."
                )
            if not test_case.steps or not all(
                step.strip() for step in test_case.steps
            ):
                raise ValueError(
                    "Each test scenario must include non-empty steps."
                )

        if self.framework == TestCodeFramework.PYTEST:
            compatible_languages = {TestCodeLanguage.PYTHON}
        else:
            compatible_languages = {
                TestCodeLanguage.PYTHON,
                TestCodeLanguage.JAVASCRIPT,
                TestCodeLanguage.TYPESCRIPT,
            }

        if self.language not in compatible_languages:
            raise ValueError(
                f"{self.framework.value} is not compatible with "
                f"{self.language.value}."
            )

        return self


class GeneratedTestCode(BaseModel):
    framework: TestCodeFramework
    language: TestCodeLanguage
    file_path: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    test_case_ids: list[str] = Field(
        default_factory=list
    )

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Generated file path must not be empty.")
        return value

    @field_validator("code")
    @classmethod
    def validate_code_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Generated code must not be empty.")
        return value

    @model_validator(mode="after")
    def validate_framework_language(self):
        if (
            self.framework == TestCodeFramework.PYTEST
            and self.language != TestCodeLanguage.PYTHON
        ):
            raise ValueError("Pytest is not supported with this language.")
        return self


class TestCodeGenerationResponse(BaseModel):
    repository_path: str
    generated_files: list[GeneratedTestCode] = Field(
        default_factory=list
    )
    total_files: int = 0
    context_available: bool = True
    context_warning: str | None = None

    @model_validator(mode="after")
    def validate_file_count(self):
        if self.total_files != len(self.generated_files):
            raise ValueError(
                "total_files must match the number of generated files."
            )
        return self


class SaveGeneratedTestCodeRequest(BaseModel):
    repository_path: str = Field(..., min_length=1)
    generated_file: GeneratedTestCode
    overwrite: bool = False


class SaveGeneratedTestCodeResponse(BaseModel):
    repository_path: str
    file_path: str
    relative_path: str
    code: str