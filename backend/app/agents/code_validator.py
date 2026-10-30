import ast
import re
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel


class CodeValidationResult(BaseModel):
    valid: bool
    language: str
    error: str | None = None
    line: int | None = None
    column: int | None = None


class GeneratedCodeValidationError(ValueError):
    """Raised when generated test code fails pre-save validation."""


class GeneratedCodeValidator:
    """Validate generated source code before it can be saved or executed."""

    SUPPORTED_LANGUAGES = {"python", "javascript", "typescript"}
    SUPPORTED_FRAMEWORKS = {"pytest", "playwright", "selenium"}

    def validate(
        self,
        code: str,
        language: str,
        framework: str | None = None,
    ) -> CodeValidationResult:
        normalized_language = language.lower().strip()
        normalized_framework = (
            framework.lower().strip() if framework else None
        )

        if normalized_language not in self.SUPPORTED_LANGUAGES:
            return self._invalid(
                normalized_language,
                "Unsupported language.",
            )

        if normalized_framework and (
            normalized_framework not in self.SUPPORTED_FRAMEWORKS
        ):
            return self._invalid(
                normalized_language,
                "Unsupported test framework.",
            )

        if not code.strip():
            return self._invalid(normalized_language, "Generated code is empty.")

        if code.lstrip().startswith("```"):
            return self._invalid(
                normalized_language,
                "Markdown fences are not valid source code.",
            )

        if (
            normalized_framework == "pytest"
            and normalized_language != "python"
        ):
            return self._invalid(
                normalized_language,
                "Pytest is not supported with this language.",
            )

        if normalized_language == "python":
            result = self._validate_python(code)
        else:
            result = self._validate_delimiters(code, normalized_language)
            if result.valid and normalized_language == "javascript":
                result = self._validate_javascript_syntax(code)
            elif result.valid and normalized_language == "typescript":
                result = self._validate_typescript_syntax(code)

        if not result.valid or normalized_framework is None:
            return result

        structure_error = self._validate_framework_structure(
            code,
            normalized_language,
            normalized_framework,
        )
        if structure_error:
            return self._invalid(normalized_language, structure_error)

        return result

    def _validate_python(
        self,
        code: str,
    ) -> CodeValidationResult:
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return CodeValidationResult(
                valid=False,
                language="python",
                error=exc.msg,
                line=exc.lineno,
                column=exc.offset,
            )

        return CodeValidationResult(valid=True, language="python")

    def _validate_delimiters(
        self,
        code: str,
        language: str,
    ) -> CodeValidationResult:
        expected_closers: list[str] = []
        pairs = {"(": ")", "[": "]", "{": "}"}
        quote: str | None = None
        escaped = False
        line_comment = False
        block_comment = False
        index = 0

        while index < len(code):
            char = code[index]
            next_char = code[index + 1] if index + 1 < len(code) else ""

            if line_comment:
                if char == "\n":
                    line_comment = False
                index += 1
                continue

            if block_comment:
                if char == "*" and next_char == "/":
                    block_comment = False
                    index += 2
                    continue
                index += 1
                continue

            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue

            if char in {"'", '"', "`"}:
                quote = char
            elif char == "/" and next_char == "/":
                line_comment = True
                index += 2
                continue
            elif char == "/" and next_char == "*":
                block_comment = True
                index += 2
                continue
            elif char in pairs:
                expected_closers.append(pairs[char])
            elif char in pairs.values():
                if not expected_closers or expected_closers.pop() != char:
                    return self._invalid(
                        language,
                        "Unexpected closing delimiter.",
                    )

            index += 1

        if quote:
            return self._invalid(language, "Unterminated string literal.")
        if block_comment:
            return self._invalid(language, "Unterminated block comment.")
        if expected_closers:
            return self._invalid(language, "Unclosed delimiter.")

        return CodeValidationResult(valid=True, language=language)

    def _validate_javascript_syntax(
        self,
        code: str,
    ) -> CodeValidationResult:
        node = shutil.which("node")
        if not node:
            return CodeValidationResult(valid=True, language="javascript")

        try:
            result = subprocess.run(
                [node, "--input-type=module", "--check", "-"],
                input=code,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._invalid(
                "javascript",
                "JavaScript syntax validation timed out.",
            )
        except OSError:
            return self._invalid(
                "javascript",
                "JavaScript syntax validation could not be started.",
            )

        if result.returncode:
            return self._invalid(
                "javascript",
                "Invalid JavaScript syntax.",
            )
        return CodeValidationResult(valid=True, language="javascript")

    def _validate_typescript_syntax(
        self,
        code: str,
    ) -> CodeValidationResult:
        node = shutil.which("node")
        typescript = (
            Path(__file__).resolve().parents[3]
            / "desktop"
            / "node_modules"
            / "typescript"
            / "lib"
            / "typescript.js"
        )
        if not node or not typescript.is_file():
            return CodeValidationResult(valid=True, language="typescript")

        parser_script = (
            "const ts=require(process.argv[1]);"
            "let source='';"
            "process.stdin.setEncoding('utf8');"
            "process.stdin.on('data',chunk=>source+=chunk);"
            "process.stdin.on('end',()=>{"
            "const result=ts.transpileModule(source,{"
            "reportDiagnostics:true,"
            "compilerOptions:{"
            "target:ts.ScriptTarget.Latest,"
            "module:ts.ModuleKind.ESNext"
            "}});"
            "const errors=(result.diagnostics||[]).filter("
            "diagnostic=>diagnostic.category===ts.DiagnosticCategory.Error"
            ");"
            "process.exitCode=errors.length?1:0;"
            "});"
        )

        try:
            result = subprocess.run(
                [node, "-e", parser_script, str(typescript)],
                input=code,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._invalid(
                "typescript",
                "TypeScript syntax validation timed out.",
            )
        except OSError:
            return self._invalid(
                "typescript",
                "TypeScript syntax validation could not be started.",
            )

        if result.returncode:
            return self._invalid("typescript", "Invalid TypeScript syntax.")
        return CodeValidationResult(valid=True, language="typescript")

    @staticmethod
    def _validate_framework_structure(
        code: str,
        language: str,
        framework: str,
    ) -> str | None:
        if framework == "pytest":
            try:
                tree = ast.parse(code)
            except SyntaxError:
                return None

            has_test = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
                for node in ast.walk(tree)
            )
            return None if has_test else "Missing pytest test structure."

        if framework == "playwright":
            if language == "python":
                has_framework_import = bool(
                    re.search(r"\b(?:from|import)\s+playwright\b", code)
                )
                has_test = bool(
                    re.search(r"\b(?:async\s+)?def\s+test_\w+\s*\(", code)
                )
            else:
                has_framework_import = bool(
                    re.search(
                        r"""(?:from\s*["']@playwright/test["']|require\(["']@playwright/test["']\))""",
                        code,
                    )
                )
                has_test = bool(re.search(r"\btest(?:\.describe)?\s*\(", code))
            if not has_framework_import or not has_test:
                return "Missing Playwright test structure."

        if framework == "selenium":
            if language == "python":
                has_framework_import = bool(
                    re.search(r"\b(?:from|import)\s+selenium\b", code)
                )
                has_driver = bool(
                    re.search(r"\bwebdriver\b", code)
                )
            else:
                has_framework_import = bool(
                    re.search(
                        r"""(?:from\s*["']selenium-webdriver["']|require\(["']selenium-webdriver["']\))""",
                        code,
                    )
                )
                has_driver = bool(
                    re.search(r"\b(?:new\s+Builder|WebDriver)\b", code)
                )
            if not has_framework_import or not has_driver:
                return "Missing Selenium test structure."

        return None

    @staticmethod
    def _invalid(language: str, error: str) -> CodeValidationResult:
        return CodeValidationResult(
            valid=False,
            language=language,
            error=error,
        )
