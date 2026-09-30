from enum import Enum

from pydantic import BaseModel, Field


class FailureType(str, Enum):
    APPLICATION_DEFECT = "application_defect"
    UI_CHANGE = "ui_change"
    INVALID_LOCATOR = "invalid_locator"
    API_CHANGE = "api_change"
    CONFIGURATION_PROBLEM = "configuration_problem"
    AUTOMATION_FAILURE = "automation_failure"
    UNKNOWN = "unknown"


class FailureAnalysisRequest(BaseModel):
    repository_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    framework: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class FailureAnalysisResult(BaseModel):
    failure_type: FailureType
    root_cause: str
    evidence: list[str]
    severity: str
    suggested_fix: str
    repair_required: bool


def analyze_failure(
    request: FailureAnalysisRequest,
) -> FailureAnalysisResult:

    text = " ".join(
        [
            request.stdout,
            request.stderr,
            request.error or "",
        ]
    ).lower()

    evidence: list[str] = []

    # Python import/module/symbol failures
    if (
        "no module named" in text
        or "modulenotfounderror" in text
        or "cannot import name" in text
        or "importerror" in text
    ):
        failure_type = FailureType.CONFIGURATION_PROBLEM
        severity = "high"

        root_cause = (
            "A required Python module, package, or imported "
            "symbol could not be resolved."
        )

        suggested_fix = (
            "Verify the Python project root, PYTHONPATH, "
            "installed dependencies, module name, and "
            "imported symbol."
        )

        evidence.append(
            "Python import or symbol-resolution failure detected."
        )

    # Selenium / Playwright locator failures
    elif (
        "no such element" in text
        or "unable to locate element" in text
        or "locator" in text
    ):
        failure_type = FailureType.INVALID_LOCATOR
        severity = "high"

        root_cause = (
            "The automation script could not locate "
            "the expected UI element."
        )

        suggested_fix = (
            "Inspect the current DOM and update the locator."
        )

        evidence.append(
            "Locator-related failure detected."
        )

    # API failures
    elif (
        "404" in text
        or "401" in text
        or "403" in text
        or "500" in text
        or ("api" in text and "error" in text)
    ):
        failure_type = FailureType.API_CHANGE
        severity = "high"

        root_cause = (
            "The test encountered an API response "
            "or API contract problem."
        )

        suggested_fix = (
            "Verify the endpoint, HTTP method, authentication, "
            "request payload, and expected response."
        )

        evidence.append(
            "API error indicators detected."
        )

    # Assertion failures
    elif (
        "assertionerror" in text
        or "assert " in text
        or "failed" in text
    ):
        failure_type = FailureType.APPLICATION_DEFECT
        severity = "medium"

        root_cause = (
            "The test assertion did not match "
            "the observed application behavior."
        )

        suggested_fix = (
            "Compare the expected behavior with the actual "
            "application behavior and inspect the related "
            "implementation."
        )

        evidence.append(
            "Test assertion or failure output detected."
        )

    # Timeout failures
    elif (
        "timeout" in text
        or "timed out" in text
    ):
        failure_type = FailureType.AUTOMATION_FAILURE
        severity = "medium"

        root_cause = (
            "The test operation exceeded "
            "its allowed execution time."
        )

        suggested_fix = (
            "Inspect synchronization, network delays, "
            "browser state, and timeout configuration."
        )

        evidence.append(
            "Timeout condition detected."
        )

    # Unknown failure
    else:
        failure_type = FailureType.UNKNOWN
        severity = "medium"

        root_cause = (
            "The available execution information was "
            "insufficient to determine a specific "
            "failure category."
        )

        suggested_fix = (
            "Inspect the complete execution log, stack trace, "
            "and affected source files."
        )

        evidence.append(
            "No known failure pattern was detected."
        )

    return FailureAnalysisResult(
        failure_type=failure_type,
        root_cause=root_cause,
        evidence=evidence,
        severity=severity,
        suggested_fix=suggested_fix,
        repair_required=True,
    )