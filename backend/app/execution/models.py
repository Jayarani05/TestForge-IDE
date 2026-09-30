from enum import Enum

from pydantic import BaseModel, Field


class ExecutionFramework(str, Enum):
    PYTEST = "pytest"
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


class ExecutionRequest(BaseModel):
    repository_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    framework: ExecutionFramework = ExecutionFramework.PYTEST
    timeout_seconds: int = Field(
        default=120,
        ge=1,
        le=3600,
    )
    args: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    repository_path: str
    file_path: str
    framework: ExecutionFramework
    status: ExecutionStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    error: str | None = None