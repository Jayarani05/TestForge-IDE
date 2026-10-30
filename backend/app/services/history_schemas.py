import json
import math
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class ExecutionHistoryItem(BaseModel):
    id: int
    execution_id: str
    repository_path: str
    file_path: str
    framework: str
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    error: str | None = None
    coverage_percent: float | None = None
    coverage_covered_statements: int | None = None
    coverage_total_statements: int | None = None
    coverage_error: str | None = None
    source_digest: str | None = None
    created_at: datetime

    @field_validator("coverage_percent")
    @classmethod
    def validate_coverage_percent(cls, value):
        if value is not None and (not 0 <= value <= 100):
            raise ValueError("Stored coverage percentage is invalid.")
        return value

    @field_validator("coverage_covered_statements", "coverage_total_statements")
    @classmethod
    def validate_coverage_statement_count(cls, value):
        if value is not None and value < 0:
            raise ValueError("Stored coverage statement count is invalid.")
        return value

    @model_validator(mode="after")
    def validate_coverage_measurement(self):
        counts = (
            self.coverage_covered_statements,
            self.coverage_total_statements,
        )
        if self.coverage_percent is None:
            if any(value is not None for value in counts):
                raise ValueError("Stored coverage counts have no measured percentage.")
        else:
            covered, total = counts
            if covered is None or total is None or total == 0 or covered > total:
                raise ValueError("Stored coverage statement counts are invalid.")
            if not math.isclose(
                self.coverage_percent,
                round(covered / total * 100, 2),
                abs_tol=0.01,
            ):
                raise ValueError("Stored coverage percentage does not match its counts.")
        if self.source_digest is not None and not re.fullmatch(
            r"[0-9a-f]{64}",
            self.source_digest,
        ):
            raise ValueError("Stored source digest is invalid.")
        return self


class FailureHistoryItem(BaseModel):
    id: int
    repository_path: str
    file_path: str
    failure_type: str
    execution_id: str | None = None
    root_cause: str | None
    observed_details: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    inferred_explanation: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    severity: str
    suggested_fix: str
    repair_required: bool
    created_at: datetime

    @field_validator("observed_details", "evidence", "recommendations", mode="before")
    @classmethod
    def decode_json_list(cls, value):
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("Stored failure history list is malformed.") from exc
            if not isinstance(decoded, list) or any(
                not isinstance(item, str) for item in decoded
            ):
                raise ValueError("Stored failure history list is malformed.")
            return decoded
        return value


class SelfHealingHistoryItem(BaseModel):
    id: int
    repair_id: str | None = None
    execution_id: str | None = None
    failure_analysis_id: int | None = None
    repository_path: str
    file_path: str
    failure_type: str
    status: str
    explanation: str
    changes: str
    original_code: str | None = None
    proposed_code: str | None = None
    review_status: str | None = None
    apply_approved: bool | None = None
    apply_outcome: str | None = None
    restore_outcome: str | None = None
    applied_at: datetime | None = None
    restored_at: datetime | None = None
    created_at: datetime


class AnalyticsHistoryItem(BaseModel):
    id: int
    repository_path: str
    test_generation_validity: float = Field(ge=0, le=100)
    coverage_before: float | None = Field(default=None, ge=0, le=100)
    coverage_after: float | None = Field(default=None, ge=0, le=100)
    coverage_improvement: float | None = Field(ge=-100, le=100)
    defect_detection_rate: float = Field(ge=0, le=100)
    development_time_reduction: float = Field(le=100)
    maintenance_reduction: float = Field(le=100)
    self_healing_success_rate: float = Field(ge=0, le=100)
    created_at: datetime

    @model_validator(mode="after")
    def validate_coverage_relationship(self):
        if self.coverage_before is None or self.coverage_after is None:
            if self.coverage_improvement is not None:
                raise ValueError(
                    "Coverage improvement requires both coverage measurements."
                )
        else:
            expected = self.coverage_after - self.coverage_before
            if self.coverage_improvement is None:
                raise ValueError(
                    "Coverage improvement is required for comparable measurements."
                )
            if not math.isclose(
                self.coverage_improvement,
                expected,
                abs_tol=0.01,
            ):
                raise ValueError(
                    "Coverage improvement does not match its measurements."
                )
        return self

    @field_validator(
        "test_generation_validity",
        "coverage_before",
        "coverage_after",
        "coverage_improvement",
        "defect_detection_rate",
        "development_time_reduction",
        "maintenance_reduction",
        "self_healing_success_rate",
    )
    @classmethod
    def reject_non_finite_metrics(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError("Stored analytics metric must be finite.")
        return value
