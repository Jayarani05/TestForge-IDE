import math
from uuid import uuid4

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class ExecutionFramework(str, Enum):
    PYTEST = "pytest"
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
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
    measure_coverage: bool = False

    @field_validator("args")
    @classmethod
    def validate_args(cls, args: list[str]) -> list[str]:
        supported = {"-q", "-v", "--disable-warnings", "-x"}
        if any(argument not in supported for argument in args):
            raise ValueError(
                "Only quiet, verbose, stop-on-first-failure, and "
                "disable-warnings runner options are supported."
            )
        return args


class ExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    repository_path: str
    file_path: str
    framework: ExecutionFramework
    status: ExecutionStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    error: str | None = None
    coverage_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    coverage_covered_statements: int | None = Field(default=None, ge=0)
    coverage_total_statements: int | None = Field(default=None, ge=0)
    coverage_error: str | None = None
    source_digest: str | None = None

    @model_validator(mode="after")
    def validate_coverage_measurement(self):
        counts = (
            self.coverage_covered_statements,
            self.coverage_total_statements,
        )
        if self.coverage_percent is None:
            if any(value is not None for value in counts):
                raise ValueError(
                    "Coverage statement counts require a measured percentage."
                )
        else:
            covered, total = counts
            if covered is None or total is None or total == 0:
                raise ValueError(
                    "Measured coverage requires a nonzero statement total."
                )
            if covered > total:
                raise ValueError(
                    "Covered statements cannot exceed total statements."
                )
            expected_percentage = round(covered / total * 100.0, 2)
            if not math.isclose(
                self.coverage_percent,
                expected_percentage,
                abs_tol=0.01,
            ):
                raise ValueError(
                    "Coverage percentage does not match the statement counts."
                )
        if self.source_digest is not None and (
            len(self.source_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.source_digest)
        ):
            raise ValueError("Source digest must be a SHA-256 hexadecimal value.")
        return self