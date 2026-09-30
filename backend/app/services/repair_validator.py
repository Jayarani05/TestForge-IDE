from pathlib import Path

from app.agents.code_validator import GeneratedCodeValidator


class RepairValidator:

    def __init__(self) -> None:
        self.code_validator = GeneratedCodeValidator()

    def validate(
        self,
        file_path: str,
        repaired_code: str,
    ) -> tuple[bool, str | None]:

        path = Path(file_path)

        if path.suffix.lower() == ".py":
            result = self.code_validator.validate(
                code=repaired_code,
                language="python",
            )

            if not result.valid:
                return False, (
                    f"Invalid Python repair: {result.error} "
                    f"(line {result.line}, column {result.column})"
                )

        return True, None