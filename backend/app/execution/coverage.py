import ast
import hashlib
import json
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


_EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "env",
    "node_modules",
    "test",
    "tests",
    "venv",
}


@dataclass(frozen=True)
class CoverageMeasurement:
    percentage: float
    covered_statements: int
    total_statements: int


def production_python_files(repository: Path) -> list[Path]:
    files = []
    for path in repository.rglob("*.py"):
        relative = path.relative_to(repository)
        if any(part.lower() in _EXCLUDED_DIRECTORY_NAMES for part in relative.parts[:-1]):
            continue
        if (
            path.name == "conftest.py"
            or path.name.startswith("test_")
            or path.name.endswith("_test.py")
        ):
            continue
        files.append(path)
    return sorted(files)


def source_digest(repository: Path) -> str | None:
    files = production_python_files(repository)
    if not files:
        return None

    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(repository).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def measure_python_statement_coverage(
    repository: Path,
    line_counts: Mapping[tuple[str, int], int],
) -> CoverageMeasurement | None:
    total_statements = 0
    covered_statements = 0
    normalized_counts = {}
    for (filename, line), count in line_counts.items():
        if (
            not isinstance(filename, str)
            or not isinstance(line, int)
            or isinstance(line, bool)
            or line < 1
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
        ):
            raise ValueError("Coverage line counts contain invalid values.")
        key = (str(Path(filename).resolve()), line)
        if key in normalized_counts:
            raise ValueError("Coverage line counts contain duplicate source lines.")
        normalized_counts[key] = count

    for path in production_python_files(repository):
        with tokenize.open(path) as source_file:
            tree = ast.parse(source_file.read(), filename=str(path))
        executable_lines = {
            node.lineno for node in ast.walk(tree) if isinstance(node, ast.stmt)
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                executable_lines.update(
                    decorator.lineno for decorator in node.decorator_list
                )
        total_statements += len(executable_lines)
        resolved_path = str(path.resolve())
        covered_statements += sum(
            normalized_counts.get((resolved_path, line), 0) > 0
            for line in executable_lines
        )

    if total_statements == 0:
        return None
    percentage = round(covered_statements / total_statements * 100.0, 2)
    if not 0 <= percentage <= 100:
        raise ValueError("Measured coverage percentage is outside the valid range.")
    return CoverageMeasurement(
        percentage=percentage,
        covered_statements=covered_statements,
        total_statements=total_statements,
    )


TRACE_RUNNER_SCRIPT = """
import json
import runpy
import sys
import trace
from pathlib import Path

output_path = Path(sys.argv[1])
repository = Path(sys.argv[2]).resolve()
arguments = sys.argv[3:]
ignored = [sys.prefix, sys.base_prefix]
ignored.extend(str(repository / name) for name in __EXCLUDED_DIRS__)
tracer = trace.Trace(count=True, trace=False, ignoredirs=ignored)
sys.argv = ["pytest", *arguments]
exit_code = 0
try:
    tracer.runctx(
        "runpy.run_module('pytest', run_name='__main__')",
        {"runpy": runpy},
        {},
    )
except SystemExit as error:
    if isinstance(error.code, int):
        exit_code = error.code
    elif error.code is not None:
        exit_code = 1

counts = [
    [filename, line, count]
    for (filename, line), count in tracer.results().counts.items()
]
try:
    output_path.write_text(
        json.dumps({"counts": counts}),
        encoding="utf-8",
    )
except OSError as error:
    print(
        "Coverage report could not be written (%s)." % type(error).__name__,
        file=sys.stderr,
    )
sys.exit(exit_code)
""".replace("__EXCLUDED_DIRS__", repr(sorted(_EXCLUDED_DIRECTORY_NAMES)))


def parse_trace_counts(path: Path) -> dict[tuple[str, int], int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Coverage trace output is missing or malformed.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("counts"), list):
        raise ValueError("Coverage trace output has an invalid structure.")

    counts: dict[tuple[str, int], int] = {}
    for entry in data["counts"]:
        if (
            not isinstance(entry, list)
            or len(entry) != 3
            or not isinstance(entry[0], str)
            or not isinstance(entry[1], int)
            or isinstance(entry[1], bool)
            or entry[1] < 1
            or not isinstance(entry[2], int)
            or isinstance(entry[2], bool)
            or entry[2] < 0
        ):
            raise ValueError("Coverage trace output contains invalid line counts.")
        key = (entry[0], entry[1])
        if key in counts:
            raise ValueError("Coverage trace output contains duplicate source lines.")
        counts[key] = entry[2]
    return counts
