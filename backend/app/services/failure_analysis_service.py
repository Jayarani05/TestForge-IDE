from collections import OrderedDict
from threading import RLock

from app.agents.failure_analysis import (
    FailureAnalysisRequest,
    FailureAnalysisResult,
    analyze_failure,
)
from app.execution.models import ExecutionResult


class FailureAnalysisService:
    MAX_ANALYSES = 200

    def __init__(self) -> None:
        self._results: OrderedDict[str, FailureAnalysisResult] = OrderedDict()
        self._lock = RLock()

    def analyze(
        self,
        request: FailureAnalysisRequest,
    ) -> FailureAnalysisResult:
        try:
            result = analyze_failure(request)
        except (TypeError, ValueError) as exc:
            raise ValueError("Execution result could not be analyzed.") from exc
        with self._lock:
            self._results[result.execution_id] = result
            self._results.move_to_end(result.execution_id)
            while len(self._results) > self.MAX_ANALYSES:
                self._results.popitem(last=False)
        return result

    def get_recorded(
        self,
        execution: ExecutionResult,
    ) -> FailureAnalysisResult | None:
        with self._lock:
            result = self._results.get(execution.execution_id)
            if result is None or result.execution_file != execution.file_path:
                return None
            self._results.move_to_end(execution.execution_id)
            return result
