from pydantic import BaseModel, Field


class RepositoryImportRequest(BaseModel):
    path: str = Field(
        ...,
        min_length=1,
        description="Absolute or relative path to the local repository.",
    )


class RepositoryInfo(BaseModel):
    name: str
    path: str
    repository_type: str
    file_count: int
    directory_count: int