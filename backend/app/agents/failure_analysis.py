import re
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.execution.models import ExecutionResult, ExecutionStatus
from app.execution.process_manager import ProcessManager


class FailureType(str, Enum):
    ASSERTION_FAILURE = "assertion_failure"
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    RUNNER_ERROR = "runner_error"
    TIMEOUT = "timeout"
    CONFIGURATION_PROBLEM = "configuration_problem"
    UNKNOWN = "unknown"


class FailureAnalysisRequest(BaseModel):
    execution: ExecutionResult

    @model_validator(mode="after")
    def require_unsuccessful_execution(self):
        if self.execution.status in {
            ExecutionStatus.PASSED,
            ExecutionStatus.SKIPPED,
            ExecutionStatus.PENDING,
            ExecutionStatus.RUNNING,
        }:
            raise ValueError("Failure analysis requires a completed unsuccessful execution.")
        return self


class FailureAnalysisResult(BaseModel):
    execution_id: str
    execution_file: str
    execution_status: ExecutionStatus
    failure_type: FailureType
    observed_details: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    root_cause: str | None = None
    inferred_explanation: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    severity: str
    repair_required: bool


def analyze_failure(
    request: FailureAnalysisRequest,
) -> FailureAnalysisResult:
    execution = request.execution
    output = ProcessManager._redact_secrets(
        "\n".join(
            part for part in (execution.stdout, execution.stderr, execution.error or "")
            if part
        ),
        None,
    )
    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]
    evidence = [line[:500] for line in lines[-12:]]
    lowered = output.lower()

    if execution.status == ExecutionStatus.TIMEOUT:
        failure_type = FailureType.TIMEOUT
        details = ["The execution result reports a timeout."]
        if execution.duration_seconds:
            details.append(
                f"Recorded execution duration: {execution.duration_seconds:.2f} seconds."
            )
        recommendation = "Review the timeout and test synchronization; no code cause is established."
    elif execution.status == ExecutionStatus.ERROR:
        runner_markers = (
            "runner executable is unavailable",
            "runner could not be started",
            "no module named pytest",
            "no module named selenium",
            "browserType.launch",
            "webdriverexception",
            "sessionnotcreatedexception",
        )
        configuration_markers = (
            "modulenotfounderror",
            "no module named",
            "cannot import name",
            "importerror",
        )
        if any(marker in lowered for marker in configuration_markers):
            failure_type = FailureType.CONFIGURATION_PROBLEM
            details = ["Execution output contains a Python import/configuration error."]
            recommendation = "Verify project configuration and dependencies before changing source."
        else:
            failure_type = FailureType.RUNNER_ERROR
            details = ["The execution result reports a runner error."]
            if any(marker in lowered for marker in runner_markers):
                details.append("Output contains a runner or browser initialization indicator.")
            recommendation = "Check runner availability and framework configuration."
    else:
        if re.search(r"\b(?:AssertionError|assertion failed|expect\(.*\)\.to)\b", output, re.I):
            failure_type = FailureType.ASSERTION_FAILURE
            details = ["Execution output contains an assertion-failure indicator."]
            recommendation = "Compare the recorded expected and actual values; available output does not identify a source-code cause."
        elif re.search(r"\b(?:SyntaxError|SyntaxError:|Syntax error)\b", output, re.I):
            failure_type = FailureType.SYNTAX_ERROR
            details = ["Execution output contains a syntax-error indicator."]
            recommendation = "Inspect the cited file and line before proposing a source change."
        elif re.search(
            r"\b(?:ModuleNotFoundError|ImportError|No module named|Cannot find module)\b",
            output,
            re.I,
        ):
            failure_type = FailureType.IMPORT_ERROR
            details = ["Execution output contains an import-resolution error."]
            recommendation = "Verify the selected project root and declared dependencies."
        elif execution.exit_code is not None and execution.exit_code != 0:
            failure_type = FailureType.UNKNOWN
            details = [f"The process exited with code {execution.exit_code}."]
            recommendation = "Inspect the captured output and test source; no specific cause is established."
        else:
            failure_type = FailureType.UNKNOWN
            details = ["The execution result contains insufficient diagnostic output."]
            recommendation = "Review the test and rerun it with appropriate diagnostic output."

    root_cause = None
    if failure_type in {FailureType.TIMEOUT, FailureType.RUNNER_ERROR}:
        root_cause = None
    elif failure_type == FailureType.UNKNOWN:
        root_cause = None

    return FailureAnalysisResult(
        execution_id=execution.execution_id,
        execution_file=execution.file_path,
        execution_status=execution.status,
        failure_type=failure_type,
        observed_details=details,
        evidence=evidence,
        root_cause=root_cause,
        inferred_explanation=None,
        recommendations=[recommendation],
        severity="high" if failure_type in {
            FailureType.CONFIGURATION_PROBLEM,
            FailureType.RUNNER_ERROR,
            FailureType.SYNTAX_ERROR,
        } else "medium",
        repair_required=failure_type in {
            FailureType.ASSERTION_FAILURE,
            FailureType.SYNTAX_ERROR,
        },
    )