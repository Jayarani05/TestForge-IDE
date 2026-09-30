from app.analytics.models import (
    AnalyticsMetrics,
    AnalyticsRecord,
    AnalyticsResponse,
)


class AnalyticsService:

    def calculate(
        self,
        record: AnalyticsRecord,
    ) -> AnalyticsResponse:

        test_generation_validity = (
            100.0 if record.test_generation_valid else 0.0
        )

        coverage_improvement = max(
            0.0,
            record.coverage_after - record.coverage_before,
        )

        if record.defects_total > 0:
            defect_detection_rate = (
                record.defects_found
                / record.defects_total
                * 100.0
            )
        else:
            defect_detection_rate = 0.0

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

        if record.self_healing_attempts > 0:
            self_healing_success_rate = (
                record.self_healing_successes
                / record.self_healing_attempts
                * 100.0
            )
        else:
            self_healing_success_rate = 0.0

        metrics = AnalyticsMetrics(
            test_generation_validity=round(
                test_generation_validity,
                2,
            ),
            coverage_improvement=round(
                coverage_improvement,
                2,
            ),
            defect_detection_rate=round(
                defect_detection_rate,
                2,
            ),
            development_time_reduction=round(
                max(0.0, development_time_reduction),
                2,
            ),
            maintenance_reduction=round(
                max(0.0, maintenance_reduction),
                2,
            ),
            self_healing_success_rate=round(
                self_healing_success_rate,
                2,
            ),
        )

        return AnalyticsResponse(
            metrics=metrics,
            record=record,
        )