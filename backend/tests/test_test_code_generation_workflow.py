from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agents.code_validator import (
    GeneratedCodeValidationError,
    GeneratedCodeValidator,
)
from app.agents.generated_file_service import GeneratedFileService
from app.agents.test_code_generation import (
    GeneratedTestCode,
    SaveGeneratedTestCodeRequest,
    TestCodeFramework,
    TestCodeGenerationRequest,
    TestCodeLanguage,
    TestCodeGenerationResponse,
)
from app.agents.test_generation import TestType
from app.api.v1 import test_generation as test_generation_api
from app.core.database import get_db
from app.main import app


def _scenario() -> dict:
    return {
        "id": "TC-001",
        "title": "Loads an order",
        "description": "Verify the order detail page shows its status.",
        "test_type": "functional",
        "priority": "medium",
        "preconditions": [],
        "steps": ["Open the order detail page."],
        "expected_result": "The order status is visible.",
    }


def _make_pytest_repository(path: Path) -> Path:
    (path / "requirements.txt").write_text("pytest==8.3.0\n", encoding="utf-8")
    (path / "tests").mkdir()
    (path / "tests" / "test_orders.py").write_text(
        "def test_order():\n    assert True\n",
        encoding="utf-8",
    )
    return path


def _request_body(repository: Path, **overrides) -> dict:
    body = {
        "repository_path": str(repository),
        "test_cases": [_scenario()],
        "framework": "pytest",
        "language": "python",
        "output_file": "tests/generated_test.py",
    }
    body.update(overrides)
    return body


@pytest.fixture
def api_client():
    async def override_get_db():
        yield object()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def _mock_context(monkeypatch, context: str = ""):
    async def retrieve(*, session, query):
        return SimpleNamespace(results=[])

    def assemble(*, query, repository_path, results):
        chunks = []
        if context:
            chunks = [
                SimpleNamespace(
                    relative_path="src/orders.py",
                    start_line=1,
                    end_line=2,
                    content=context,
                )
            ]
        return SimpleNamespace(chunks=chunks)

    monkeypatch.setattr(
        test_generation_api.hybrid_retriever,
        "retrieve",
        retrieve,
    )
    monkeypatch.setattr(
        test_generation_api.context_assembler,
        "assemble",
        assemble,
    )


def test_generate_code_returns_validated_code_without_saving(
    api_client,
    monkeypatch,
    tmp_path,
):
    repository = _make_pytest_repository(tmp_path)
    _mock_context(monkeypatch, "def get_order_status(): ...")
    captured = {}

    async def generate(*, request, test_cases, context, orchestrator):
        captured["context"] = context
        captured["test_cases"] = test_cases
        generated = GeneratedTestCode(
            framework=TestCodeFramework.PYTEST,
            language=TestCodeLanguage.PYTHON,
            file_path=request.output_file,
            code="def test_order_status():\n    assert True",
            test_case_ids=[test_cases[0].id],
        )
        return TestCodeGenerationResponse(
            repository_path=request.repository_path,
            generated_files=[generated],
            total_files=1,
            context_available=bool(context),
        )

    monkeypatch.setattr(test_generation_api.test_code_generator, "generate", generate)

    response = api_client.post(
        "/tests/generate-code",
        json=_request_body(repository),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total_files"] == 1
    assert result["generated_files"][0]["code"].startswith("def test_")
    assert captured["context"].startswith("File: src/orders.py")
    assert captured["test_cases"][0].id == "TC-001"
    assert not (repository / "tests" / "generated_test.py").exists()


def test_generate_code_reports_empty_repository_context(
    api_client,
    monkeypatch,
    tmp_path,
):
    repository = _make_pytest_repository(tmp_path)
    _mock_context(monkeypatch)

    async def generate(*, request, test_cases, context, orchestrator):
        assert context == ""
        return TestCodeGenerationResponse(
            repository_path=request.repository_path,
            generated_files=[
                GeneratedTestCode(
                    framework=request.framework,
                    language=request.language,
                    file_path=request.output_file,
                    code="def test_scenario():\n    assert True",
                    test_case_ids=["TC-001"],
                )
            ],
            total_files=1,
            context_available=False,
            context_warning="No repository context was retrieved.",
        )

    monkeypatch.setattr(test_generation_api.test_code_generator, "generate", generate)

    response = api_client.post(
        "/tests/generate-code",
        json=_request_body(repository),
    )

    assert response.status_code == 200
    assert response.json()["context_available"] is False
    assert "No repository context" in response.json()["context_warning"]


@pytest.mark.parametrize(
    "body, expected_message",
    [
        ({"test_cases": []}, "at least 1 item"),
        ({"test_cases": [{**_scenario(), "title": " "}]}, "id, title"),
        (
            {"framework": "pytest", "language": "typescript"},
            "not compatible",
        ),
    ],
)
def test_generate_code_rejects_invalid_requests(
    api_client,
    tmp_path,
    body,
    expected_message,
):
    repository = _make_pytest_repository(tmp_path)
    response = api_client.post(
        "/tests/generate-code",
        json=_request_body(repository, **body),
    )

    assert response.status_code == 422
    assert expected_message in response.text


def test_generate_code_rejects_unsupported_framework_evidence(
    api_client,
    monkeypatch,
    tmp_path,
):
    repository = _make_pytest_repository(tmp_path)
    _mock_context(monkeypatch)
    response = api_client.post(
        "/tests/generate-code",
        json=_request_body(
            repository,
            framework="selenium",
        ),
    )

    assert response.status_code == 422
    assert "No repository evidence supports selenium" in response.text


def test_generate_code_hides_provider_failure_details(
    api_client,
    monkeypatch,
    tmp_path,
):
    repository = _make_pytest_repository(tmp_path)
    _mock_context(monkeypatch)

    async def generate(*args, **kwargs):
        raise RuntimeError("provider-secret-token")

    monkeypatch.setattr(test_generation_api.test_code_generator, "generate", generate)
    response = api_client.post(
        "/tests/generate-code",
        json=_request_body(repository),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Test-code generation failed. Review the request and retry."
    )
    assert "provider-secret-token" not in response.text


def test_generate_code_reports_validation_failure_separately(
    api_client,
    monkeypatch,
    tmp_path,
):
    repository = _make_pytest_repository(tmp_path)
    _mock_context(monkeypatch)

    async def generate(*args, **kwargs):
        raise GeneratedCodeValidationError(
            "Generated code validation failed at line 1: invalid syntax"
        )

    monkeypatch.setattr(test_generation_api.test_code_generator, "generate", generate)
    response = api_client.post(
        "/tests/generate-code",
        json=_request_body(repository),
    )

    assert response.status_code == 422
    assert "Generated code validation failed at line 1" in response.json()["detail"]


@pytest.mark.parametrize(
    "language, framework, code",
    [
        ("python", "pytest", "def test_order():\n    assert True"),
        (
            "javascript",
            "playwright",
            'import { test, expect } from "@playwright/test";\ntest("order", async ({ page }) => { await expect(page).toHaveTitle("Orders"); });',
        ),
        (
            "typescript",
            "selenium",
            'import { Builder } from "selenium-webdriver";\nconst driver = new Builder().forBrowser("chrome").build();',
        ),
    ],
)
def test_generated_code_validator_accepts_framework_structures(
    language,
    framework,
    code,
):
    result = GeneratedCodeValidator().validate(
        code=code,
        language=language,
        framework=framework,
    )

    assert result.valid is True


@pytest.mark.parametrize(
    "code, language, framework, message",
    [
        ("  ", "python", "pytest", "empty"),
        ("def test_bad(:\n    pass", "python", "pytest", "invalid syntax"),
        ("const x = {", "javascript", "playwright", "Unclosed delimiter"),
        ("```python\ndef test_fenced(): pass\n```", "python", "pytest", "Markdown fences"),
        ("def example():\n    pass", "python", "pytest", "test structure"),
        (
            "def test_order():\n    assert True",
            "python",
            "junit",
            "Unsupported test framework",
        ),
        (
            "def test_order():\n    assert True",
            "typescript",
            "pytest",
            "not supported",
        ),
    ],
)
def test_generated_code_validator_rejects_invalid_output(
    code,
    language,
    framework,
    message,
):
    result = GeneratedCodeValidator().validate(
        code=code,
        language=language,
        framework=framework,
    )

    assert result.valid is False
    assert message.lower() in (result.error or "").lower()


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js syntax checker is unavailable.",
)
def test_generated_code_validator_rejects_invalid_javascript_syntax():
    result = GeneratedCodeValidator().validate(
        code="const = broken;",
        language="javascript",
        framework="playwright",
    )

    assert result.valid is False
    assert result.error == "Invalid JavaScript syntax."


@pytest.mark.skipif(
    shutil.which("node") is None
    or not (
        Path(__file__).resolve().parents[2]
        / "desktop"
        / "node_modules"
        / "typescript"
        / "lib"
        / "typescript.js"
    ).is_file(),
    reason="TypeScript syntax checker is unavailable.",
)
def test_generated_code_validator_rejects_invalid_typescript_syntax():
    result = GeneratedCodeValidator().validate(
        code=(
            'import { Builder } from "selenium-webdriver";\n'
            "const = broken;\n"
            "const driver = new Builder().build();"
        ),
        language="typescript",
        framework="selenium",
    )

    assert result.valid is False
    assert result.error == "Invalid TypeScript syntax."


def _generated_file(file_path: str, code: str = "def test_saved():\n    assert True"):
    return GeneratedTestCode(
        framework=TestCodeFramework.PYTEST,
        language=TestCodeLanguage.PYTHON,
        file_path=file_path,
        code=code,
        test_case_ids=["TC-001"],
    )


def test_generated_file_service_saves_within_repository(tmp_path):
    saved_path = GeneratedFileService().save(
        str(tmp_path),
        _generated_file("tests/generated_test.py"),
    )

    assert Path(saved_path) == tmp_path / "tests" / "generated_test.py"
    assert Path(saved_path).read_text(encoding="utf-8") == (
        "def test_saved():\n    assert True"
    )


@pytest.mark.parametrize(
    "file_path",
    [
        "../outside.py",
        "..\\outside.py",
        "C:\\outside.py",
        "tests\\NUL.py",
        "tests\\bad?.py",
        "",
    ],
)
def test_generated_file_service_rejects_unsafe_names(tmp_path, file_path):
    with pytest.raises(ValueError):
        GeneratedFileService().save(
            str(tmp_path),
            _generated_file(file_path),
        )


def test_generated_file_service_conflict_preserves_existing_content(tmp_path):
    target = tmp_path / "tests" / "generated_test.py"
    target.parent.mkdir()
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        GeneratedFileService().save(
            str(tmp_path),
            _generated_file("tests/generated_test.py"),
        )

    assert target.read_text(encoding="utf-8") == "existing"

    GeneratedFileService().save(
        str(tmp_path),
        _generated_file("tests/generated_test.py", "replacement"),
        overwrite=True,
    )
    assert target.read_text(encoding="utf-8") == "replacement"


def test_generated_file_service_reports_write_failure(tmp_path):
    (tmp_path / "tests").write_text("not a directory", encoding="utf-8")

    with pytest.raises(OSError):
        GeneratedFileService().save(
            str(tmp_path),
            _generated_file("tests/generated_test.py"),
        )


def test_save_generated_code_endpoint_requires_explicit_overwrite(
    api_client,
    tmp_path,
):
    target = tmp_path / "tests" / "generated_test.py"
    target.parent.mkdir()
    target.write_text("original", encoding="utf-8")
    generated_file = _generated_file("tests/generated_test.py")

    first_response = api_client.post(
        "/tests/save-code",
        json=SaveGeneratedTestCodeRequest(
            repository_path=str(tmp_path),
            generated_file=generated_file,
        ).model_dump(mode="json"),
    )
    assert first_response.status_code == 409
    assert target.read_text(encoding="utf-8") == "original"

    overwrite_response = api_client.post(
        "/tests/save-code",
        json=SaveGeneratedTestCodeRequest(
            repository_path=str(tmp_path),
            generated_file=generated_file,
            overwrite=True,
        ).model_dump(mode="json"),
    )
    assert overwrite_response.status_code == 200
    saved = overwrite_response.json()
    assert Path(saved["file_path"]) == target
    assert saved["code"] == target.read_text(encoding="utf-8")


def test_save_generated_code_endpoint_rejects_path_traversal(
    api_client,
    tmp_path,
):
    response = api_client.post(
        "/tests/save-code",
        json={
            "repository_path": str(tmp_path),
            "generated_file": _generated_file("../outside.py").model_dump(mode="json"),
        },
    )

    assert response.status_code == 422
    assert "traversal" in response.text


def test_save_generated_code_endpoint_rejects_invalid_code(
    api_client,
    tmp_path,
):
    generated_file = _generated_file(
        "tests/invalid_test.py",
        "def test_invalid(:\n    pass",
    )
    response = api_client.post(
        "/tests/save-code",
        json={
            "repository_path": str(tmp_path),
            "generated_file": generated_file.model_dump(mode="json"),
        },
    )

    assert response.status_code == 422
    assert "Generated code validation failed" in response.json()["detail"]
    assert not (tmp_path / "tests" / "invalid_test.py").exists()


def test_save_generated_code_endpoint_reports_write_failure(
    api_client,
    tmp_path,
):
    (tmp_path / "tests").write_text("not a directory", encoding="utf-8")
    response = api_client.post(
        "/tests/save-code",
        json={
            "repository_path": str(tmp_path),
            "generated_file": _generated_file(
                "tests/generated_test.py"
            ).model_dump(mode="json"),
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Generated test file could not be saved."
