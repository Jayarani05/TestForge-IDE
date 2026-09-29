import ast

from pydantic import BaseModel


class CodeValidationResult(BaseModel):
    valid: bool
    language: str
    error: str | None = None
    line: int | None = None
    column: int | None = None


class GeneratedCodeValidator:
    """Validate generated source code before it can be saved or executed."""

    def validate(
        self,
        code: str,
        language: str,
    ) -> CodeValidationResult:
        normalized_language = language.lower().strip()

        if normalized_language == "python":
            return self._validate_python(code)

        # JavaScript and TypeScript validation will be added
        # when their code-generation pipelines are implemented.
        return CodeValidationResult(
            valid=True,
            language=normalized_language,
        )

    def _validate_python(
        self,
        code: str,
    ) -> CodeValidationResult:
        try:
            ast.parse(code)

            return CodeValidationResult(
                valid=True,
                language="python",
            )

        except SyntaxError as exc:
            return CodeValidationResult(
                valid=False,
                language="python",
                error=exc.msg,
                line=exc.lineno,
                column=exc.offset,
            )