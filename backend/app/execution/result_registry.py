from collections import OrderedDict
from threading import RLock

from app.execution.models import ExecutionResult


class ExecutionResultRegistry:
    """Keep a bounded set of recent results for same-execution analysis."""

    MAX_RESULTS = 200

    def __init__(self) -> None:
        self._results: OrderedDict[str, ExecutionResult] = OrderedDict()
        self._lock = RLock()

    def store(self, result: ExecutionResult) -> None:
        with self._lock:
            self._results[result.execution_id] = result
            self._results.move_to_end(result.execution_id)
            while len(self._results) > self.MAX_RESULTS:
                self._results.popitem(last=False)

    def get(self, execution_id: str) -> ExecutionResult | None:
        with self._lock:
            result = self._results.get(execution_id)
            if result is not None:
                self._results.move_to_end(execution_id)
            return result


execution_result_registry = ExecutionResultRegistry()
