from pydantic import BaseModel, Field


class AnalyticsRecord(BaseModel):
    repository_path: str
    test_generation_valid: bool = False

    coverage_before: float = Field(default=0.0, ge=0.0, le=100.0)
    coverage_after: float = Field(default=0.0, ge=0.0, le=100.0)

    defects_found: int = Field(default=0, ge=0)
    defects_total: int = Field(default=0, ge=0)

    development_time_before_minutes: float = Field(default=0.0, ge=0.0)
    development_time_after_minutes: float = Field(default=0.0, ge=0.0)

    maintenance_events_before: int = Field(default=0, ge=0)
    maintenance_events_after: int = Field(default=0, ge=0)

    self_healing_attempts: int = Field(default=0, ge=0)
    self_healing_successes: int = Field(default=0, ge=0)


class AnalyticsMetrics(BaseModel):
    test_generation_validity: float
    coverage_improvement: float
    defect_detection_rate: float
    development_time_reduction: float
    maintenance_reduction: float
    self_healing_success_rate: float


class AnalyticsResponse(BaseModel):
    metrics: AnalyticsMetrics
    record: AnalyticsRecord