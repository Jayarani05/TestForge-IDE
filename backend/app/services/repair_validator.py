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

        languages = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
        }
        language = languages.get(path.suffix.lower())
        if language is None:
            return False, "Unsupported repair file type."
        result = self.code_validator.validate(
            code=repaired_code,
            language=language,
        )

        if not result.valid:
            return False, (
                f"Invalid {language} repair: {result.error} "
                f"(line {result.line}, column {result.column})"
            )

        return True, None