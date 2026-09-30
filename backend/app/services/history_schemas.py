from datetime import datetime

from pydantic import BaseModel


class ExecutionHistoryItem(BaseModel):
    id: int
    repository_path: str
    file_path: str
    framework: str
    status: str
    exit_code: int | None
    duration_seconds: float
    created_at: datetime


class FailureHistoryItem(BaseModel):
    id: int
    repository_path: str
    file_path: str
    failure_type: str
    root_cause: str
    severity: str
    suggested_fix: str
    repair_required: bool
    created_at: datetime


class SelfHealingHistoryItem(BaseModel):
    id: int
    repository_path: str
    file_path: str
    failure_type: str
    status: str
    explanation: str
    changes: str
    created_at: datetime


class AnalyticsHistoryItem(BaseModel):
    id: int
    repository_path: str
    test_generation_validity: float
    coverage_improvement: float
    defect_detection_rate: float
    development_time_reduction: float
    maintenance_reduction: float
    self_healing_success_rate: float
    created_at: datetime
