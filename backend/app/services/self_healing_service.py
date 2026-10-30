import json
import os
import uuid
from pathlib import Path
from typing import Any

from app.agents.providers import LLMRequest
from app.agents.self_healing import (
    RepairOperationResult,
    RepairStatus,
    SelfHealingRequest,
    SelfHealingResult,
)
from app.agents.orchestrator import LLMOrchestrator
from app.execution.process_manager import ProcessManager
from app.services.repair_file_service import RepairFileService
from app.services.repair_validator import RepairValidator


class SelfHealingService:
    MAX_SOURCE_BYTES = 256_000

    def __init__(
        self,
        orchestrator: LLMOrchestrator | None = None,
        repair_file_service: RepairFileService | None = None,
        repair_validator: RepairValidator | None = None,
    ) -> None:
        self.orchestrator = orchestrator or LLMOrchestrator()
        self.repair_files = repair_file_service or RepairFileService()
        self.repair_validator = repair_validator or RepairValidator()

    async def repair(
        self,
        request: SelfHealingRequest,
    ) -> SelfHealingResult:
        repository, target, relative_path = self._resolve_source(
            request.repository_path,
            request.execution.file_path,
        )
        source_bytes = target.read_bytes()
        if len(source_bytes) > self.MAX_SOURCE_BYTES:
            raise ValueError("Repair target exceeds the supported source size.")
        try:
            original_code = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Repair target must be UTF-8 encoded text.") from exc

        safe_source = ProcessManager._redact_secrets(original_code, os.environ)
        if safe_source != original_code:
            raise ValueError(
                "Repair generation was stopped because the source contains a secret-like value."
            )
        evidence = [
            ProcessManager._redact_secrets(item, os.environ)
            for item in request.analysis.evidence
        ]
        prompt = (
            "Generate a minimal repair candidate for the failed test execution below. "
            "Return only a JSON object with keys repaired_code, explanation, changes, "
            "target_line_start, target_line_end. Do not apply or execute the repair. "
            "Use null for unknown line numbers. Do not invent evidence.\n\n"
            f"Test file: {relative_path}\n"
            f"Framework: {request.execution.framework.value}\n"
            f"Exit code: {request.execution.exit_code}\n"
            f"Failure type: {request.analysis.failure_type.value}\n"
            f"Observed details: {json.dumps(request.analysis.observed_details)}\n"
            f"Evidence: {json.dumps(evidence)}\n"
            f"Original source:\n{original_code}"
        )
        try:
            response = await self.orchestrator.generate(
                LLMRequest(
                    prompt=prompt,
                    system_prompt=(
                        "Propose code only when supported by the failure evidence. "
                        "Do not claim a fix is proven. Preserve unrelated source."
                    ),
                    temperature=0.1,
                    max_tokens=8192,
                ),
                provider_name=request.provider,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Repair candidate generation failed ({type(exc).__name__})."
            ) from exc
        result = self._parse_candidate(response.content)

        proposed_code = ProcessManager._redact_secrets(
            result["repaired_code"],
            os.environ,
        )
        if proposed_code != result["repaired_code"]:
            raise ValueError("Generated repair candidate contains secret-like data.")
        if proposed_code == original_code:
            raise ValueError("Generated repair candidate does not change the source.")
        valid, validation_message = self.repair_validator.validate(
            str(target),
            proposed_code,
        )
        if not valid:
            raise ValueError(
                f"Generated repair candidate failed validation: {validation_message}"
            )

        start = result["target_line_start"]
        end = result["target_line_end"]
        line_count = len(original_code.splitlines())
        if start is not None and (start < 1 or start > line_count):
            raise ValueError("Repair candidate target start line is outside the source.")
        if end is not None and (
            end < 1 or end > line_count or (start is not None and end < start)
        ):
            raise ValueError("Repair candidate target end line is invalid.")

        repair_id = str(uuid.uuid4())
        self.repair_files.register_candidate(
            repair_id,
            str(repository),
            relative_path,
            original_code,
            proposed_code,
        )
        return SelfHealingResult(
            repair_id=repair_id,
            file_path=relative_path,
            target_line_start=start,
            target_line_end=end,
            original_code=original_code,
            repaired_code=proposed_code,
            explanation=result["explanation"],
            changes=result["changes"],
            evidence=evidence,
            eligible_for_review=True,
        )

    def apply(
        self,
        repair_id: str,
        approved: bool,
    ) -> RepairOperationResult:
        code, relative_path = self.repair_files.apply_repair(
            repair_id,
            approved,
        )
        return RepairOperationResult(
            repair_id=repair_id,
            status=RepairStatus.APPLIED,
            file_path=relative_path,
            code=code,
            message="Repair applied after explicit approval.",
        )

    def restore(self, repair_id: str) -> RepairOperationResult:
        code, relative_path = self.repair_files.restore_backup(repair_id)
        return RepairOperationResult(
            repair_id=repair_id,
            status=RepairStatus.RESTORED,
            file_path=relative_path,
            code=code,
            message="The source was restored to its pre-repair contents.",
        )

    @staticmethod
    def _resolve_source(
        repository_path: str,
        file_path: str,
    ) -> tuple[Path, Path, str]:
        from app.services.repair_file_service import RepairFileService

        repository, target, relative_path = RepairFileService()._resolve_target(
            repository_path,
            file_path,
        )
        return repository, target, relative_path

    @staticmethod
    def _parse_candidate(content: str) -> dict[str, Any]:
        try:
            candidate = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Repair provider returned malformed JSON.") from exc
        if not isinstance(candidate, dict):
            raise ValueError("Repair provider response must be a JSON object.")
        code = candidate.get("repaired_code")
        explanation = candidate.get("explanation")
        changes = candidate.get("changes")
        start = candidate.get("target_line_start")
        end = candidate.get("target_line_end")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("Repair provider response omitted repaired_code.")
        if not isinstance(explanation, str) or not explanation.strip():
            raise ValueError("Repair provider response omitted an explanation.")
        if (
            not isinstance(changes, list)
            or not changes
            or any(not isinstance(change, str) or not change.strip() for change in changes)
        ):
            raise ValueError("Repair provider response must include non-empty changes.")
        if any(value is not None and (not isinstance(value, int) or isinstance(value, bool))
               for value in (start, end)):
            raise ValueError("Repair target line numbers must be integers or null.")
        sanitized = [
            ProcessManager._redact_secrets(value, os.environ)
            for value in [explanation, *changes]
        ]
        if sanitized != [explanation, *changes]:
            raise ValueError("Repair provider response contains secret-like data.")
        return {
            "repaired_code": code,
            "explanation": explanation,
            "changes": changes,
            "target_line_start": start,
            "target_line_end": end,
        }
