from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.agents.failure_analysis import FailureAnalysisResult
from app.execution.models import ExecutionResult, ExecutionStatus


class RepairStatus(str, Enum):
    GENERATED = "generated"
    APPLIED = "applied"
    RESTORED = "restored"


class SelfHealingRequest(BaseModel):
    repository_path: str = Field(..., min_length=1)
    execution: ExecutionResult
    analysis: FailureAnalysisResult
    provider: str = "auto"

    @model_validator(mode="after")
    def validate_repair_evidence(self):
        if self.execution.status != ExecutionStatus.FAILED:
            raise ValueError("Repair candidates require a failed test execution.")
        if self.execution.file_path != self.analysis.execution_file:
            raise ValueError("Failure analysis does not match the execution file.")
        if self.execution.execution_id != self.analysis.execution_id:
            raise ValueError("Failure analysis does not match the execution identifier.")
        if not self.analysis.repair_required:
            raise ValueError("The failure analysis does not support a repair candidate.")
        if not self.analysis.evidence:
            raise ValueError("Failure analysis must include supporting evidence.")
        return self


class SelfHealingResult(BaseModel):
    repair_id: str
    status: RepairStatus = RepairStatus.GENERATED
    file_path: str
    target_line_start: int | None = None
    target_line_end: int | None = None
    original_code: str
    repaired_code: str
    explanation: str
    changes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    eligible_for_review: bool = True


class RepairApplyRequest(BaseModel):
    repair_id: str = Field(..., min_length=1)
    approved: bool


class RepairOperationResult(BaseModel):
    repair_id: str
    status: RepairStatus
    file_path: str
    code: str
    message: str
