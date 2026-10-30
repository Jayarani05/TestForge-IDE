from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import repository as repository_api
from app.repository import tree_service as tree_service_module
from app.main import app


client = TestClient(app)


def test_repository_tree_returns_project_files_and_ignores_generated_dirs(
    tmp_path,
):
    (tmp_path / "src").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "node_modules" / "dependency").mkdir(
        parents=True
    )
    (tmp_path / ".cache" / "tool").mkdir(parents=True)
    (tmp_path / "build" / "generated").mkdir(
        parents=True
    )

    for relative_path in (
        "src/main.py",
        ".github/workflows/ci.yml",
        "README.md",
        "openapi.yaml",
        "node_modules/dependency/index.js",
        ".cache/tool/cache.json",
        "build/generated/output.js",
    ):
        file_path = tmp_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("fixture", encoding="utf-8")

    response = client.get(
        "/repository/tree",
        params={"path": str(tmp_path)},
    )

    assert response.status_code == 200
    tree = response.json()
    assert tree["repository_path"] == str(tmp_path.resolve())

    relative_files = {
        item["relative_path"].replace("\\", "/")
        for item in tree["files"]
    }
    assert {
        "src/main.py",
        ".github/workflows/ci.yml",
        "README.md",
        "openapi.yaml",
    }.issubset(relative_files)
    assert not any(
        path.startswith(
            ("node_modules/", ".cache/", "build/")
        )
        for path in relative_files
    )
    assert not (tmp_path / "outputs").exists()


def test_repository_tree_does_not_follow_symlinks_outside_root(
    tmp_path,
):
    repository = tmp_path / "repository"
    external = tmp_path / "external"
    repository.mkdir()
    external.mkdir()
    (external / "outside.py").write_text(
        "external",
        encoding="utf-8",
    )

    link = repository / "external-link"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError as exc:
        pytest.skip(
            f"Directory symlinks unavailable in this environment: "
            f"{type(exc).__name__}"
        )

    response = client.get(
        "/repository/tree",
        params={"path": str(repository)},
    )

    assert response.status_code == 200
    tree = response.json()
    assert all(
        "outside.py" not in item["relative_path"]
        for item in tree["files"]
    )
    assert all(
        item["relative_path"] != "external-link"
        for item in tree["directories"]
    )


def test_repository_tree_prunes_symlink_directories_before_descent(
    tmp_path,
    monkeypatch,
):
    repository = tmp_path / "repository"
    source = repository / "src"
    source.mkdir(parents=True)
    (source / "inside.py").write_text(
        "inside",
        encoding="utf-8",
    )
    symlink_directory = repository / "external-link"

    original_is_symlink = Path.is_symlink

    def is_symlink(path):
        if path == symlink_directory:
            return True
        return original_is_symlink(path)

    def simulated_walk(root, *, onerror, followlinks):
        assert followlinks is False
        directories = ["external-link", "src"]
        yield str(root), directories, []
        assert directories == ["src"]
        yield str(source), [], ["inside.py"]

    monkeypatch.setattr(Path, "is_symlink", is_symlink)
    monkeypatch.setattr(
        tree_service_module.os,
        "walk",
        simulated_walk,
    )

    response = client.get(
        "/repository/tree",
        params={"path": str(repository)},
    )

    assert response.status_code == 200
    tree = response.json()
    assert [
        item["relative_path"].replace("\\", "/")
        for item in tree["files"]
    ] == ["src/inside.py"]
    assert [
        item["relative_path"].replace("\\", "/")
        for item in tree["directories"]
    ] == ["src"]


def test_repository_tree_reports_invalid_paths(tmp_path):
    missing_response = client.get(
        "/repository/tree",
        params={"path": str(tmp_path / "missing")},
    )
    file_path = tmp_path / "not-a-directory.txt"
    file_path.write_text("fixture", encoding="utf-8")
    file_response = client.get(
        "/repository/tree",
        params={"path": str(file_path)},
    )
    missing_parameter_response = client.get(
        "/repository/tree",
    )

    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == (
        "Repository path does not exist."
    )
    assert file_response.status_code == 400
    assert file_response.json()["detail"] == (
        "Repository path must be a directory."
    )
    assert missing_parameter_response.status_code == 422


def test_repository_tree_reports_permission_errors(
    monkeypatch,
):
    def inaccessible_walk(*_args, **kwargs):
        kwargs["onerror"](PermissionError("access denied"))
        return iter(())

    monkeypatch.setattr(
        tree_service_module.os,
        "walk",
        inaccessible_walk,
    )

    response = client.get(
        "/repository/tree",
        params={"path": "."},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission denied while accessing the repository."
    )


def test_repository_tree_parameter_matches_endpoint_contract():
    route = next(
        route
        for route in app.routes
        if route.path == "/repository/tree"
        and "GET" in route.methods
    )

    assert route.dependant.query_params[0].name == "path"
