import math
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.context.embeddings import HashEmbeddingProvider
from app.core.database import get_db
from app.main import app


def _embedding_text(vector: list[float]) -> str:
    return ",".join(str(value) for value in vector)


def _record(
    repository_path: str,
    relative_path: str,
    embedding: list[float],
    *,
    score_label: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        repository_path=repository_path,
        file_path=str(Path(repository_path) / relative_path),
        relative_path=relative_path,
        content=f"content for {score_label}",
        source_type="source_code",
        language="Python",
        start_line=4,
        end_line=9,
        chunk_type="file_segment",
        embedding=_embedding_text(embedding),
    )


@pytest.fixture
def retrieval_client():
    session = SimpleNamespace(execute=AsyncMock())

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize(
    ("endpoint", "score_scale"),
    [
        ("/context/retrieve", 1.0),
        ("/context/hybrid-retrieve", 0.6),
    ],
)
def test_persistent_retrieval_ranks_limits_and_preserves_metadata(
    tmp_path,
    retrieval_client,
    endpoint,
    score_scale,
):
    client, session = retrieval_client
    repository = (tmp_path / "repository").resolve()
    other_repository = (tmp_path / "other-repository").resolve()
    repository.mkdir()
    other_repository.mkdir()

    provider = HashEmbeddingProvider(dimension=128)
    query_vector = provider.embed_text("needle")
    query_index = query_vector.index(max(query_vector))
    orthogonal_index = next(
        index
        for index in range(len(query_vector))
        if index != query_index
    )

    medium_vector = [0.0] * len(query_vector)
    medium_vector[query_index] = 1.0
    medium_vector[orthogonal_index] = 1.0
    magnitude = math.sqrt(2.0)
    medium_vector = [
        value / magnitude
        for value in medium_vector
    ]

    unrelated_vector = [0.0] * len(query_vector)
    unrelated_vector[orthogonal_index] = 1.0

    records = [
        _record(
            str(repository),
            "src/medium.py",
            medium_vector,
            score_label="medium",
        ),
        _record(
            str(repository),
            "src/high.py",
            query_vector,
            score_label="high",
        ),
        _record(
            str(repository),
            "src/unrelated.py",
            unrelated_vector,
            score_label="unrelated",
        ),
        _record(
            str(other_repository),
            "src/other.py",
            query_vector,
            score_label="other repository",
        ),
    ]

    async def execute(statement):
        parameters = statement.compile().params
        requested_path = next(
            value
            for value in parameters.values()
            if value == str(repository)
            or value == os.path.relpath(repository, Path.cwd())
        )
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(
                all=lambda: [
                    record
                    for record in records
                    if record.repository_path == requested_path
                ]
            )
        )

    session.execute.side_effect = execute
    relative_repository_path = os.path.relpath(
        repository,
        Path.cwd(),
    )

    response = client.post(
        endpoint,
        json={
            "query": "needle",
            "repository_path": relative_repository_path,
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["repository_path"] == str(repository)
    assert body["total_results"] == 2
    assert [
        result["chunk"]["relative_path"]
        for result in body["results"]
    ] == ["src/high.py", "src/medium.py"]
    assert [
        result["score"]
        for result in body["results"]
    ] == pytest.approx(
        [
            score_scale,
            score_scale / math.sqrt(2),
        ]
    )

    high_result = body["results"][0]
    assert high_result["chunk"] == {
        "repository_path": str(repository),
        "file_path": str(repository / "src" / "high.py"),
        "relative_path": "src/high.py",
        "content": "content for high",
        "source_type": "source_code",
        "language": "Python",
        "start_line": 4,
        "end_line": 9,
        "symbol_name": None,
        "chunk_type": "file_segment",
        "metadata": {},
    }


def test_persistent_retrieval_returns_empty_index(
    tmp_path,
    retrieval_client,
):
    client, session = retrieval_client
    repository = tmp_path / "empty-repository"

    session.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )

    response = client.post(
        "/context/retrieve",
        json={
            "query": "anything",
            "repository_path": str(repository),
        },
    )

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["total_results"] == 0


def test_context_assembly_returns_canonical_path_for_empty_index(
    tmp_path,
    retrieval_client,
):
    client, session = retrieval_client
    repository = (tmp_path / "empty-repository").resolve()
    repository.mkdir()
    session.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )

    response = client.post(
        "/context/assemble",
        json={
            "query": "anything",
            "repository_path": os.path.relpath(
                repository,
                Path.cwd(),
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["repository_path"] == str(repository)
    assert response.json()["total_chunks"] == 0
    assert response.json()["chunks"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {
            "query": "",
            "repository_path": "repository",
        },
        {
            "query": "needle",
            "repository_path": "repository",
            "top_k": 0,
        },
        {
            "query": "needle",
            "repository_path": "repository",
            "top_k": 101,
        },
    ],
)
def test_persistent_retrieval_rejects_invalid_query_parameters(
    retrieval_client,
    payload,
):
    client, session = retrieval_client

    response = client.post(
        "/context/retrieve",
        json=payload,
    )

    assert response.status_code == 422
    session.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "stored_embedding",
    ["malformed", "1.0,not-a-number", "1.0,0.0"],
)
def test_persistent_retrieval_reports_malformed_stored_vectors(
    tmp_path,
    retrieval_client,
    stored_embedding,
):
    client, session = retrieval_client
    repository = tmp_path / "repository"
    repository.mkdir()
    record = _record(
        str(repository),
        "src/module.py",
        [1.0],
        score_label="malformed",
    )
    record.embedding = stored_embedding
    session.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [record])
    )

    response = client.post(
        "/context/retrieve",
        json={
            "query": "needle",
            "repository_path": str(repository),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] in {
        "could not convert string to float: 'malformed'",
        "could not convert string to float: 'not-a-number'",
        "Vectors must have the same dimension.",
    }
