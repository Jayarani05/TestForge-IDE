import pytest
from pydantic import ValidationError

from app.analytics.models import AnalyticsRecord
from app.analytics.service import AnalyticsService


def test_analytics_calculates_metrics_from_record_values():
    record = AnalyticsRecord(
        repository_path="repo",
        test_generation_valid=True,
        coverage_before=40,
        coverage_after=62.5,
        defects_found=3,
        defects_total=4,
        development_time_before_minutes=80,
        development_time_after_minutes=60,
        maintenance_events_before=10,
        maintenance_events_after=7,
        self_healing_attempts=5,
        self_healing_successes=3,
    )

    metrics = AnalyticsService().calculate(record).metrics

    assert metrics.test_generation_validity == 100
    assert metrics.coverage_improvement == 22.5
    assert metrics.defect_detection_rate == 75
    assert metrics.development_time_reduction == 25
    assert metrics.maintenance_reduction == 30
    assert metrics.self_healing_success_rate == 60


def test_analytics_distinguishes_unavailable_coverage_from_zero_denominators():
    metrics = AnalyticsService().calculate(
        AnalyticsRecord(repository_path="repo")
    ).metrics

    assert metrics.test_generation_validity == 0
    assert metrics.coverage_improvement is None
    assert metrics.defect_detection_rate == 0
    assert metrics.development_time_reduction == 0
    assert metrics.maintenance_reduction == 0
    assert metrics.self_healing_success_rate == 0


def test_analytics_reports_zero_improvement_for_equal_measured_coverage():
    metrics = AnalyticsService().calculate(
        AnalyticsRecord(
            repository_path="repo",
            coverage_before=40,
            coverage_after=40,
        )
    ).metrics

    assert metrics.coverage_improvement == 0


@pytest.mark.parametrize(
    "values",
    [
        {"defects_found": 2, "defects_total": 1},
        {"self_healing_attempts": 1, "self_healing_successes": 2},
    ],
)
def test_analytics_rejects_success_counts_above_their_denominator(values):
    with pytest.raises(ValidationError):
        AnalyticsRecord(repository_path="repo", **values)
