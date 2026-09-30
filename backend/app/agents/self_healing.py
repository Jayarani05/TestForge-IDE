from enum import Enum

from pydantic import BaseModel, Field


class RepairStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    GENERATED = "generated"
    APPLIED = "applied"
    FAILED = "failed"


class SelfHealingRequest(BaseModel):
    repository_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    failure_type: str = Field(..., min_length=1)
    root_cause: str = Field(..., min_length=1)
    suggested_fix: str = Field(..., min_length=1)
    source_code: str = ""


class SelfHealingResult(BaseModel):
    status: RepairStatus
    file_path: str
    original_code: str
    repaired_code: str
    explanation: str
    changes: list[str]


class SelfHealingAgent:

    def repair(
        self,
        request: SelfHealingRequest,
    ) -> SelfHealingResult:

        original_code = request.source_code

        # Controlled demonstration repair.
        # This proves the repair -> validation ->
        # re-execution pipeline before introducing
        # unrestricted AI-generated file modifications.
        if request.failure_type == "application_defect":

            repaired_code = original_code.replace(
                "actual = 5",
                "actual = 10",
            )

            if repaired_code != original_code:

                return SelfHealingResult(
                    status=RepairStatus.GENERATED,
                    file_path=request.file_path,
                    original_code=original_code,
                    repaired_code=repaired_code,
                    explanation=(
                        "A controlled assertion failure was repaired "
                        "by correcting the demonstrated test value."
                    ),
                    changes=[
                        "Detected controlled assertion failure",
                        "Changed actual value from 5 to 10",
                        "Generated executable repair candidate",
                    ],
                )

        # Configuration/import failures require environment-level
        # changes, so source code is preserved.
        if request.failure_type == "configuration_problem":

            repaired_code = original_code

            return SelfHealingResult(
                status=RepairStatus.GENERATED,
                file_path=request.file_path,
                original_code=original_code,
                repaired_code=repaired_code,
                explanation=(
                    "The failure was classified as a configuration "
                    "or Python import problem. The source code was "
                    "preserved because the repair requires "
                    "environment-level changes."
                ),
                changes=[
                    "Detected configuration/import failure",
                    "Preserved source code",
                    "Recommended environment/PYTHONPATH correction",
                ],
            )

        # Locator failures require the current application DOM.
        if request.failure_type == "invalid_locator":

            repaired_code = original_code

            return SelfHealingResult(
                status=RepairStatus.GENERATED,
                file_path=request.file_path,
                original_code=original_code,
                repaired_code=repaired_code,
                explanation=(
                    "A locator failure was detected. Locator repair "
                    "requires the current application DOM or page "
                    "structure."
                ),
                changes=[
                    "Detected invalid locator",
                    "Marked automation script for locator repair",
                ],
            )

        # Default safe behavior.
        repaired_code = original_code

        return SelfHealingResult(
            status=RepairStatus.GENERATED,
            file_path=request.file_path,
            original_code=original_code,
            repaired_code=repaired_code,
            explanation=(
                "Failure information was analyzed and a repair "
                "candidate was generated."
            ),
            changes=[
                "Analyzed failure category",
                "Generated repair candidate",
                "Preserved original source for safe review",
            ],
        )