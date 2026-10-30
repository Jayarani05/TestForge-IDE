import math

from pydantic import BaseModel, Field, model_validator


class AnalyticsRecord(BaseModel):
    repository_path: str

    test_generation_valid: bool = False

    coverage_before: float | None = Field(default=None, ge=0.0, le=100.0)

    coverage_after: float | None = Field(default=None, ge=0.0, le=100.0)

    defects_found: int = Field(
        default=0,
        ge=0,
    )

    defects_total: int = Field(
        default=0,
        ge=0,
    )

    development_time_before_minutes: float = Field(
        default=0.0,
        ge=0.0,
    )

    development_time_after_minutes: float = Field(
        default=0.0,
        ge=0.0,
    )

    maintenance_events_before: int = Field(
        default=0,
        ge=0,
    )

    maintenance_events_after: int = Field(
        default=0,
        ge=0,
    )

    self_healing_attempts: int = Field(
        default=0,
        ge=0,
    )

    self_healing_successes: int = Field(
        default=0,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_metric_counts(self):
        if self.defects_found > self.defects_total:
            raise ValueError("defects_found cannot exceed defects_total.")
        if self.self_healing_successes > self.self_healing_attempts:
            raise ValueError(
                "self_healing_successes cannot exceed self_healing_attempts."
            )
        return self

    @model_validator(mode="after")
    def validate_coverage_values(self):
        for value in (self.coverage_before, self.coverage_after):
            if value is not None and not math.isfinite(value):
                raise ValueError("Coverage values must be finite percentages.")
        return self


class AnalyticsMetrics(BaseModel):
    test_generation_validity: float
    coverage_improvement: float | None
    defect_detection_rate: float
    development_time_reduction: float
    maintenance_reduction: float
    self_healing_success_rate: float


class AnalyticsResponse(BaseModel):
    metrics: AnalyticsMetrics
    record: AnalyticsRecord


class SelfHealingMetricRequest(BaseModel):
    repository_path: str = Field(..., min_length=1)

    attempted: bool = True

    successful: bool = False


class SelfHealingMetricResponse(BaseModel):
    repository_path: str

    attempts: int

    successes: int

    success_rate: float