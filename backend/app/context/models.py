from enum import Enum

from pydantic import BaseModel, Field


class ContextSourceType(str, Enum):
    SOURCE_CODE = "source_code"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    API_SPECIFICATION = "api_specification"
    TEST = "test"
    AUTOMATION = "automation"


class ContextChunk(BaseModel):
    repository_path: str
    file_path: str
    relative_path: str
    content: str

    source_type: ContextSourceType
    language: str | None = None

    start_line: int | None = None
    end_line: int | None = None

    symbol_name: str | None = None
    chunk_type: str | None = None

    metadata: dict[str, str] = Field(default_factory=dict)


class ContextQuery(BaseModel):
    query: str = Field(..., min_length=1)

    repository_path: str

    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
    )

    source_types: list[ContextSourceType] = Field(
        default_factory=list
    )

    languages: list[str] = Field(
        default_factory=list
    )


class ContextResult(BaseModel):
    chunk: ContextChunk

    score: float = Field(
        ge=0.0,
        le=1.0,
    )


class ContextResponse(BaseModel):
    query: str
    repository_path: str

    results: list[ContextResult] = Field(
        default_factory=list
    )

    total_results: int = 0


class ContextAssembly(BaseModel):
    query: str
    repository_path: str

    chunks: list[ContextChunk] = Field(
        default_factory=list
    )

    total_chunks: int = 0
    estimated_tokens: int = 0