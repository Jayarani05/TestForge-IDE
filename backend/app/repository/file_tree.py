from pydantic import BaseModel


class RepositoryFile(BaseModel):
    name: str
    path: str
    relative_path: str
    extension: str | None
    language: str | None
    size_bytes: int


class RepositoryDirectory(BaseModel):
    name: str
    path: str
    relative_path: str


class RepositoryTree(BaseModel):
    repository_path: str
    files: list[RepositoryFile]
    directories: list[RepositoryDirectory]
