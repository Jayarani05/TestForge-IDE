from app.analytics.models import (
    AnalyticsMetrics,
    AnalyticsRecord,
    AnalyticsResponse,
    SelfHealingMetricRequest,
    SelfHealingMetricResponse,
)


class AnalyticsService:

    def calculate(
        self,
        record: AnalyticsRecord,
    ) -> AnalyticsResponse:

        # Test-generation validity
        test_generation_validity = (
            100.0 if record.test_generation_valid else 0.0
        )

        # Coverage improvement
        coverage_improvement = None
        if (
            record.coverage_before is not None
            and record.coverage_after is not None
        ):
            coverage_improvement = (
                record.coverage_after - record.coverage_before
            )

        # Defect detection rate
        if record.defects_total > 0:
            defect_detection_rate = (
                record.defects_found
                / record.defects_total
                * 100.0
            )
        else:
            defect_detection_rate = 0.0

        # Development-time reduction
        if record.development_time_before_minutes > 0:
            development_time_reduction = (
                (
                    record.development_time_before_minutes
                    - record.development_time_after_minutes
                )
                / record.development_time_before_minutes
                * 100.0
            )
        else:
            development_time_reduction = 0.0

        # Maintenance reduction
        if record.maintenance_events_before > 0:
            maintenance_reduction = (
                (
                    record.maintenance_events_before
                    - record.maintenance_events_after
                )
                / record.maintenance_events_before
                * 100.0
            )
        else:
            maintenance_reduction = 0.0

        # Self-healing success rate
        if record.self_healing_attempts > 0:
            self_healing_success_rate = (
                record.self_healing_successes
                / record.self_healing_attempts
                * 100.0
            )
        else:
            self_healing_success_rate = 0.0

        metrics = AnalyticsMetrics(
            test_generation_validity=test_generation_validity,
            coverage_improvement=coverage_improvement,
            defect_detection_rate=defect_detection_rate,
            development_time_reduction=development_time_reduction,
            maintenance_reduction=maintenance_reduction,
            self_healing_success_rate=self_healing_success_rate,
        )

        return AnalyticsResponse(
            metrics=metrics,
            record=record,
        )

    def calculate_self_healing_metric(
        self,
        request: SelfHealingMetricRequest,
    ) -> SelfHealingMetricResponse:

        attempts = 1 if request.attempted else 0

        successes = (
            1
            if request.attempted and request.successful
            else 0
        )

        if attempts > 0:
            success_rate = (
                successes / attempts * 100.0
            )
        else:
            success_rate = 0.0

        return SelfHealingMetricResponse(
            repository_path=request.repository_path,
            attempts=attempts,
            successes=successes,
            success_rate=success_rate,
        )