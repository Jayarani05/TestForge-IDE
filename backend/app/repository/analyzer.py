from pydantic import BaseModel, Field


class DependencyInfo(BaseModel):
    name: str
    version: str | None = None
    source_file: str


class TestFileInfo(BaseModel):
    path: str
    framework: str | None = None
    language: str | None = None


class ApiSpecificationInfo(BaseModel):
    path: str
    specification_type: str


class ConfigurationFileInfo(BaseModel):
    path: str
    configuration_type: str


class DocumentationFileInfo(BaseModel):
    path: str
    documentation_type: str


class AutomationFileInfo(BaseModel):
    path: str
    automation_type: str


class ProjectInfo(BaseModel):
    name: str
    path: str
    project_type: str

    languages: list[str] = Field(
        default_factory=list
    )

    frameworks: list[str] = Field(
        default_factory=list
    )

    dependency_files: list[str] = Field(
        default_factory=list
    )


class RepositoryAnalysis(BaseModel):
    repository_path: str

    project_name: str

    project_type: str = "multi-project"

    projects: list[ProjectInfo] = Field(
        default_factory=list
    )

    languages: list[str] = Field(
        default_factory=list
    )

    frameworks: list[str] = Field(
        default_factory=list
    )

    dependencies: list[DependencyInfo] = Field(
        default_factory=list
    )

    configuration_files: list[ConfigurationFileInfo] = Field(
        default_factory=list
    )

    api_specifications: list[ApiSpecificationInfo] = Field(
        default_factory=list
    )

    documentation_files: list[DocumentationFileInfo] = Field(
        default_factory=list
    )

    test_files: list[TestFileInfo] = Field(
        default_factory=list
    )

    automation_files: list[AutomationFileInfo] = Field(
        default_factory=list
    )
