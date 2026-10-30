from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TestExecutionRecord(Base):
    __tablename__ = "test_executions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    execution_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
    )

    repository_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    framework: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    stdout: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )

    stderr: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )

    duration_seconds: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    coverage_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    coverage_covered_statements: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    coverage_total_statements: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    coverage_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_digest: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class FailureAnalysisRecord(Base):
    __tablename__ = "failure_analyses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    execution_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("test_executions.execution_id"),
        nullable=True,
        unique=True,
    )

    repository_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    failure_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    root_cause: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    observed_details: Mapped[str] = mapped_column(
        Text,
        default="[]",
        nullable=False,
    )

    evidence: Mapped[str] = mapped_column(
        Text,
        default="[]",
        nullable=False,
    )

    inferred_explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recommendations: Mapped[str] = mapped_column(
        Text,
        default="[]",
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    suggested_fix: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    repair_required: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class SelfHealingRecord(Base):
    __tablename__ = "self_healing_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    repair_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        unique=True,
    )

    execution_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("test_executions.execution_id"),
        nullable=True,
    )

    failure_analysis_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("failure_analyses.id"),
        nullable=True,
    )

    repository_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    failure_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    explanation: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )

    changes: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )

    original_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    proposed_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    review_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    apply_approved: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    apply_outcome: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    restore_outcome: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    restored_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class AnalyticsRecordDB(Base):
    __tablename__ = "analytics_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    repository_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    test_generation_validity: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    coverage_before: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    coverage_after: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    coverage_improvement: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    defect_detection_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    development_time_reduction: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    maintenance_reduction: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    self_healing_success_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )