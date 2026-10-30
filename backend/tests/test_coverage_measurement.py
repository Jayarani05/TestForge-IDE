import asyncio

from pydantic import ValidationError
import pytest

from app.execution.coverage import (
    measure_python_statement_coverage,
    parse_trace_counts,
)
from app.execution.models import ExecutionResult, ExecutionStatus
from app.execution.pytest_executor import PytestExecutor


def test_statement_coverage_uses_executable_source_lines(tmp_path):
    source = tmp_path / "app" / "logic.py"
    source.parent.mkdir()
    source.write_text(
        "def calculate(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n",
        encoding="utf-8",
    )

    measurement = measure_python_statement_coverage(
        tmp_path,
        {(str(source), 1): 1, (str(source), 2): 1, (str(source), 3): 1},
    )

    assert measurement is not None
    assert measurement.covered_statements == 3
    assert measurement.total_statements == 4
    assert measurement.percentage == 75


def test_statement_coverage_is_unavailable_without_production_source(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_only.py").write_text(
        "def test_value():\n    assert True\n",
        encoding="utf-8",
    )

    assert measure_python_statement_coverage(tmp_path, {}) is None


def test_statement_coverage_rejects_invalid_line_counts(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid values"):
        measure_python_statement_coverage(
            tmp_path,
            {(str(source), 1): -1},
        )


def test_trace_parser_rejects_malformed_and_impossible_counts(tmp_path):
    trace_output = tmp_path / "trace.json"
    trace_output.write_text('{"counts": [[1, 2]]}', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid line counts"):
        parse_trace_counts(trace_output)

    trace_output.write_text(
        '{"counts": [["source.py", 1, 1], ["source.py", 1, 2]]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate source lines"):
        parse_trace_counts(trace_output)

    trace_output.write_text(
        '{"counts": [["source.py", 1, -1]]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid line counts"):
        parse_trace_counts(trace_output)


def test_execution_result_rejects_inconsistent_coverage_values():
    with pytest.raises(ValidationError, match="does not match"):
        ExecutionResult(
            repository_path="repo",
            file_path="tests/test_sample.py",
            framework="pytest",
            status=ExecutionStatus.PASSED,
            coverage_percent=50,
            coverage_covered_statements=1,
            coverage_total_statements=3,
        )

    with pytest.raises(ValidationError, match="cannot exceed"):
        ExecutionResult(
            repository_path="repo",
            file_path="tests/test_sample.py",
            framework="pytest",
            status=ExecutionStatus.PASSED,
            coverage_percent=100,
            coverage_covered_statements=2,
            coverage_total_statements=1,
        )


def test_pytest_executor_measures_real_coverage_from_temporary_fixture(tmp_path):
    app = tmp_path / "app"
    tests = tmp_path / "tests"
    app.mkdir()
    tests.mkdir()
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "logic.py").write_text(
        "def calculate(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n",
        encoding="utf-8",
    )
    (tests / "test_logic.py").write_text(
        "from app.logic import calculate\n\n"
        "def test_calculate():\n"
        "    assert calculate(True) == 1\n",
        encoding="utf-8",
    )

    result = asyncio.run(
        PytestExecutor().execute(
            repository_path=str(tmp_path),
            file_path="tests/test_logic.py",
            measure_coverage=True,
        )
    )

    assert result.status == ExecutionStatus.PASSED
    assert result.coverage_error is None
    assert result.coverage_percent == 75
    assert result.coverage_covered_statements == 3
    assert result.coverage_total_statements == 4
    assert result.source_digest is not None


def test_pytest_executor_returns_unavailable_for_test_only_repository(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_only.py").write_text(
        "def test_value():\n    assert True\n",
        encoding="utf-8",
    )

    result = asyncio.run(
        PytestExecutor().execute(
            repository_path=str(tmp_path),
            file_path="tests/test_only.py",
            measure_coverage=True,
        )
    )

    assert result.status == ExecutionStatus.PASSED
    assert result.coverage_percent is None
    assert result.coverage_covered_statements is None
    assert result.coverage_total_statements is None
    assert "No production Python source" in (result.coverage_error or "")
