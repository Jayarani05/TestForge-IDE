import json

from fastapi.testclient import TestClient

from app.api.v1 import repository as repository_api
from app.core.database import get_db
from app.main import app
from app.repository.schemas import RepositoryInfo


client = TestClient(app)


def test_analyze_route_is_registered():
    assert any(
        route.path == "/repository/analyze"
        and "POST" in route.methods
        for route in app.routes
    )


def test_analyze_repository_returns_structured_real_analysis(
    tmp_path,
):
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "fixture-project",
                "dependencies": {
                    "react": "^18.0.0",
                },
                "devDependencies": {
                    "vite": "^5.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text(
        "export const value = 1;\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "main.test.ts").write_text(
        "test('works', () => {});\n",
        encoding="utf-8",
    )
    secret_value = "task12-fixture-secret-value"
    (tmp_path / ".env").write_text(
        f"API_KEY={secret_value}\n",
        encoding="utf-8",
    )
    (tmp_path / "notes.txt").write_text(
        "Unrelated local file content",
        encoding="utf-8",
    )

    response = client.post(
        "/repository/analyze",
        json={"path": str(tmp_path)},
    )

    assert response.status_code == 200
    analysis = response.json()
    assert analysis["project_name"] == tmp_path.name
    assert analysis["project_type"] == "node"
    assert "TypeScript" in analysis["languages"]
    assert {"React", "Vite"}.issubset(
        set(analysis["frameworks"])
    )
    assert [
        dependency["name"]
        for dependency in analysis["dependencies"]
    ] == ["react", "vite"]
    assert analysis["test_files"][0]["path"].replace(
        "\\",
        "/",
    ) == "tests/main.test.ts"
    assert secret_value not in response.text
    assert "Unrelated local file content" not in response.text


def test_analyze_repository_detects_artifacts_through_api(
    tmp_path,
):
    repository_path = tmp_path / "fixture-repository"
    (repository_path / "tests").mkdir(parents=True)
    (repository_path / "automation").mkdir()

    fixture_files = {
        "vite.config.ts": "export default {};\n",
        "README.md": "# Fixture repository\n",
        "openapi.yaml": "openapi: 3.0.0\n",
        "tests/test_sample.py": "def test_sample(): pass\n",
        "automation/playwright.config.ts": "export default {};\n",
    }
    for relative_path, content in fixture_files.items():
        (repository_path / relative_path).write_text(
            content,
            encoding="utf-8",
        )

    (tmp_path / "outside-playwright.config.ts").write_text(
        "export default {};\n",
        encoding="utf-8",
    )

    response = client.post(
        "/repository/analyze",
        json={"path": str(repository_path)},
    )

    assert response.status_code == 200
    analysis = response.json()

    assert {
        (
            item["path"].replace("\\", "/"),
            item["configuration_type"],
        )
        for item in analysis["configuration_files"]
    } == {("vite.config.ts", "Vite")}
    assert {
        (
            item["path"].replace("\\", "/"),
            item["specification_type"],
        )
        for item in analysis["api_specifications"]
    } == {("openapi.yaml", "OpenAPI")}
    assert {
        (
            item["path"].replace("\\", "/"),
            item["documentation_type"],
        )
        for item in analysis["documentation_files"]
    } == {("README.md", "README")}
    assert {
        (
            item["path"].replace("\\", "/"),
            item["framework"],
            item["language"],
        )
        for item in analysis["test_files"]
    } == {("tests/test_sample.py", "Pytest", "Python")}
    assert {
        (
            item["path"].replace("\\", "/"),
            item["automation_type"],
        )
        for item in analysis["automation_files"]
    } == {
        ("automation/playwright.config.ts", "Playwright")
    }


def test_analyze_repository_rejects_invalid_paths(tmp_path):
    empty_path_response = client.post(
        "/repository/analyze",
        json={"path": ""},
    )
    missing_path_response = client.post(
        "/repository/analyze",
        json={"path": str(tmp_path / "missing")},
    )
    file_path = tmp_path / "not-a-directory.txt"
    file_path.write_text("content", encoding="utf-8")
    file_path_response = client.post(
        "/repository/analyze",
        json={"path": str(file_path)},
    )

    assert empty_path_response.status_code == 422
    assert missing_path_response.status_code == 404
    assert missing_path_response.json()["detail"] == (
        "Repository path does not exist."
    )
    assert file_path_response.status_code == 400
    assert file_path_response.json()["detail"] == (
        "Repository path must be a directory."
    )


def test_existing_repository_routes_remain_available(
    tmp_path,
    monkeypatch,
):
    expected_info = RepositoryInfo(
        name=tmp_path.name,
        path=str(tmp_path),
        repository_type="unknown",
        file_count=1,
        directory_count=0,
    )
    (tmp_path / "README.md").write_text(
        "fixture",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repository_api.repository_service,
        "inspect_repository",
        lambda _path: expected_info,
    )

    async def save_repository(_session, _repository_info):
        return None

    monkeypatch.setattr(
        repository_api.repository_service,
        "save_repository",
        save_repository,
    )

    async def override_get_db():
        yield None

    monkeypatch.setitem(
        app.dependency_overrides,
        get_db,
        override_get_db,
    )

    inspect_response = client.post(
        "/repository/inspect",
        json={"path": str(tmp_path)},
    )
    tree_response = client.get(
        "/repository/tree",
        params={"path": str(tmp_path)},
    )

    assert inspect_response.status_code == 200
    assert inspect_response.json()["name"] == tmp_path.name
    assert tree_response.status_code == 200
    assert any(
        item["relative_path"] == "README.md"
        for item in tree_response.json()["files"]
    )
