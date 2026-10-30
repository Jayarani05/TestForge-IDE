from collections.abc import AsyncGenerator
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import context as context_api
from app.core.database import get_db
from app.main import app
from app.models.context_embedding import ContextEmbedding


@pytest.fixture
def context_index_client():
    session = SimpleNamespace(
        execute=AsyncMock(),
        add_all=Mock(),
        commit=AsyncMock(),
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_context_index_persists_real_repository_chunks(
    tmp_path,
    context_index_client,
):
    client, session = context_index_client
    repository = tmp_path / "repository"
    source_file = repository / "src" / "service.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(
        b"def service():\r\n    return 'indexed'\r\n"
    )
    (repository / "src" / "image.png").write_bytes(
        b"\x89PNG\r\n\x1a\n"
    )
    dependency_file = (
        repository / "node_modules" / "package" / "index.js"
    )
    dependency_file.parent.mkdir(parents=True)
    dependency_file.write_text(
        "dependency",
        encoding="utf-8",
    )
    relative_repository_path = os.path.relpath(
        repository,
        Path.cwd(),
    )

    response = client.post(
        "/context/index",
        json={"path": relative_repository_path},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "repository_path": str(repository.resolve()),
        "chunks_created": 1,
        "chunks_indexed": 1,
        "embedding_dimension": 128,
    }

    records = session.add_all.call_args.args[0]
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, ContextEmbedding)
    assert record.repository_path == str(repository.resolve())
    assert record.file_path == str(source_file)
    assert record.relative_path == "src/service.py"
    assert record.content == "def service():\n    return 'indexed'"
    assert record.source_type == "source_code"
    assert record.language == "Python"
    assert record.start_line == 1
    assert record.end_line == 2
    assert record.embedding_dimension == 128
    assert len(record.embedding.split(",")) == 128
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()

    session.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(
            all=lambda: records
        )
    )
    retrieval_response = client.post(
        "/context/retrieve",
        json={
            "query": "return",
            "repository_path": response.json()[
                "repository_path"
            ],
            "top_k": 5,
        },
    )

    assert retrieval_response.status_code == 200
    retrieved = retrieval_response.json()
    assert retrieved["total_results"] == 1
    assert retrieved["results"][0]["chunk"]["relative_path"] == (
        "src/service.py"
    )
    assert retrieved["results"][0]["chunk"]["content"] == (
        "def service():\n    return 'indexed'"
    )


def test_hash_embeddings_are_stable_across_processes():
    script = (
        "import json; "
        "from app.context.embeddings import HashEmbeddingProvider; "
        "print(json.dumps("
        "HashEmbeddingProvider(16).embed_text('repository context')"
        "))"
    )
    backend_directory = Path(__file__).resolve().parents[1]
    outputs = []

    for hash_seed in ("1", "2"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = hash_seed
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_directory,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(json.loads(result.stdout))

    assert outputs[0] == outputs[1]
    assert len(outputs[0]) == 16


@pytest.mark.parametrize(
    "include_binary_file",
    [False, True],
)
def test_empty_context_index_replaces_previous_repository_index(
    tmp_path,
    context_index_client,
    include_binary_file,
):
    client, session = context_index_client
    repository = tmp_path / "empty-repository"
    repository.mkdir()
    if include_binary_file:
        (repository / "image.png").write_bytes(
            b"\x89PNG\r\n\x1a\n"
        )

    response = client.post(
        "/context/index",
        json={"path": str(repository)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "repository_path": str(repository),
        "chunks_created": 0,
        "chunks_indexed": 0,
        "embedding_dimension": 128,
    }
    session.execute.assert_awaited_once()
    session.add_all.assert_called_once_with([])
    session.commit.assert_awaited_once()


@pytest.mark.parametrize(
    ("path_kind", "expected_status", "expected_detail"),
    [
        ("missing", 404, "Repository path does not exist."),
        ("file", 400, "Repository path must be a directory."),
    ],
)
def test_context_index_preserves_invalid_path_api_errors(
    tmp_path,
    context_index_client,
    path_kind,
    expected_status,
    expected_detail,
):
    client, session = context_index_client
    repository_path = tmp_path / "missing"

    if path_kind == "file":
        repository_path.write_text(
            "not a directory",
            encoding="utf-8",
        )

    response = client.post(
        "/context/index",
        json={"path": str(repository_path)},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_context_index_maps_repository_permission_errors(
    tmp_path,
    context_index_client,
    monkeypatch,
):
    client, session = context_index_client

    def raise_permission_error(_repository_path):
        raise PermissionError("access denied")

    monkeypatch.setattr(
        context_api.chunking_service,
        "chunk_repository",
        raise_permission_error,
    )

    response = client.post(
        "/context/index",
        json={"path": str(tmp_path)},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission denied while indexing repository context."
    )
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()
