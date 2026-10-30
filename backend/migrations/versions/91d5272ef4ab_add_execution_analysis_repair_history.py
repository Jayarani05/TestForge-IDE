"""add durable execution, analysis, repair and coverage history

Revision ID: 91d5272ef4ab
Revises: 7c6644be5d28
Create Date: 2026-10-30 21:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91d5272ef4ab"
down_revision: Union[str, Sequence[str], None] = "7c6644be5d28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_executions",
        sa.Column("execution_id", sa.String(length=36), nullable=True),
    )
    op.execute(
        "UPDATE test_executions "
        "SET execution_id = 'legacy-' || CAST(id AS VARCHAR) "
        "WHERE execution_id IS NULL"
    )
    op.alter_column("test_executions", "execution_id", nullable=False)
    op.create_unique_constraint(
        "uq_test_executions_execution_id",
        "test_executions",
        ["execution_id"],
    )
    op.add_column(
        "test_executions",
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.add_column(
        "test_executions",
        sa.Column("coverage_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "test_executions",
        sa.Column("coverage_covered_statements", sa.Integer(), nullable=True),
    )
    op.add_column(
        "test_executions",
        sa.Column("coverage_total_statements", sa.Integer(), nullable=True),
    )
    op.add_column(
        "test_executions",
        sa.Column("coverage_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "test_executions",
        sa.Column("source_digest", sa.String(length=64), nullable=True),
    )

    op.add_column(
        "failure_analyses",
        sa.Column("execution_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_failure_analyses_execution_id",
        "failure_analyses",
        "test_executions",
        ["execution_id"],
        ["execution_id"],
    )
    op.create_unique_constraint(
        "uq_failure_analyses_execution_id",
        "failure_analyses",
        ["execution_id"],
    )
    op.alter_column("failure_analyses", "root_cause", nullable=True)
    op.add_column(
        "failure_analyses",
        sa.Column("observed_details", sa.Text(), nullable=True),
    )
    op.add_column(
        "failure_analyses",
        sa.Column("evidence", sa.Text(), nullable=True),
    )
    op.add_column(
        "failure_analyses",
        sa.Column("inferred_explanation", sa.Text(), nullable=True),
    )
    op.add_column(
        "failure_analyses",
        sa.Column("recommendations", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE failure_analyses SET observed_details = '[]' "
        "WHERE observed_details IS NULL"
    )
    op.execute(
        "UPDATE failure_analyses SET evidence = '[]' WHERE evidence IS NULL"
    )
    op.execute(
        "UPDATE failure_analyses SET recommendations = '[]' "
        "WHERE recommendations IS NULL"
    )
    op.alter_column("failure_analyses", "observed_details", nullable=False)
    op.alter_column("failure_analyses", "evidence", nullable=False)
    op.alter_column("failure_analyses", "recommendations", nullable=False)

    op.add_column(
        "self_healing_runs",
        sa.Column("repair_id", sa.String(length=36), nullable=True),
    )
    op.create_unique_constraint(
        "uq_self_healing_runs_repair_id",
        "self_healing_runs",
        ["repair_id"],
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("execution_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_self_healing_runs_execution_id",
        "self_healing_runs",
        "test_executions",
        ["execution_id"],
        ["execution_id"],
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("failure_analysis_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_self_healing_runs_failure_analysis_id",
        "self_healing_runs",
        "failure_analyses",
        ["failure_analysis_id"],
        ["id"],
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("original_code", sa.Text(), nullable=True),
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("proposed_code", sa.Text(), nullable=True),
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("review_status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("apply_approved", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("apply_outcome", sa.Text(), nullable=True),
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("restore_outcome", sa.Text(), nullable=True),
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("applied_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "self_healing_runs",
        sa.Column("restored_at", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "analytics_records",
        sa.Column("coverage_before", sa.Float(), nullable=True),
    )
    op.add_column(
        "analytics_records",
        sa.Column("coverage_after", sa.Float(), nullable=True),
    )
    op.alter_column("analytics_records", "coverage_improvement", nullable=True)


def downgrade() -> None:
    op.alter_column("analytics_records", "coverage_improvement", nullable=False)
    op.drop_column("analytics_records", "coverage_after")
    op.drop_column("analytics_records", "coverage_before")

    op.drop_column("self_healing_runs", "restored_at")
    op.drop_column("self_healing_runs", "applied_at")
    op.drop_column("self_healing_runs", "restore_outcome")
    op.drop_column("self_healing_runs", "apply_outcome")
    op.drop_column("self_healing_runs", "apply_approved")
    op.drop_column("self_healing_runs", "review_status")
    op.drop_column("self_healing_runs", "proposed_code")
    op.drop_column("self_healing_runs", "original_code")
    op.drop_constraint(
        "fk_self_healing_runs_failure_analysis_id",
        "self_healing_runs",
        type_="foreignkey",
    )
    op.drop_column("self_healing_runs", "failure_analysis_id")
    op.drop_constraint(
        "fk_self_healing_runs_execution_id",
        "self_healing_runs",
        type_="foreignkey",
    )
    op.drop_column("self_healing_runs", "execution_id")
    op.drop_constraint(
        "uq_self_healing_runs_repair_id",
        "self_healing_runs",
        type_="unique",
    )
    op.drop_column("self_healing_runs", "repair_id")

    op.drop_column("failure_analyses", "recommendations")
    op.drop_column("failure_analyses", "inferred_explanation")
    op.drop_column("failure_analyses", "evidence")
    op.drop_column("failure_analyses", "observed_details")
    op.alter_column("failure_analyses", "root_cause", nullable=False)
    op.drop_constraint(
        "uq_failure_analyses_execution_id",
        "failure_analyses",
        type_="unique",
    )
    op.drop_constraint(
        "fk_failure_analyses_execution_id",
        "failure_analyses",
        type_="foreignkey",
    )
    op.drop_column("failure_analyses", "execution_id")

    op.drop_column("test_executions", "source_digest")
    op.drop_column("test_executions", "coverage_error")
    op.drop_column("test_executions", "coverage_total_statements")
    op.drop_column("test_executions", "coverage_covered_statements")
    op.drop_column("test_executions", "coverage_percent")
    op.drop_column("test_executions", "error")
    op.drop_constraint(
        "uq_test_executions_execution_id",
        "test_executions",
        type_="unique",
    )
    op.drop_column("test_executions", "execution_id")
