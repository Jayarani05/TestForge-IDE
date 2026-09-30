from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TestExecutionRecord(Base):
    __tablename__ = "test_executions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
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

    root_cause: Mapped[str] = mapped_column(
        Text,
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

    coverage_improvement: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
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