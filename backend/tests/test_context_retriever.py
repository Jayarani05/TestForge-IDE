from pathlib import Path

from app.context import (
    ContextChunkingService,
    ContextQuery,
    ContextRetriever,
)


REPOSITORY_ROOT = (
    Path(__file__).resolve().parents[2]
)


def test_repository_analysis_query_retrieves_analyzer():
    chunks = ContextChunkingService().chunk_repository(
        REPOSITORY_ROOT
    )

    query = ContextQuery(
        query="How does TestForge analyze a repository?",
        repository_path=str(REPOSITORY_ROOT),
        top_k=5,
    )

    response = ContextRetriever().retrieve(
        chunks,
        query,
    )

    assert response.total_results > 0
    assert len(response.results) <= 5

    top_paths = [
        result.chunk.relative_path.lower()
        for result in response.results
    ]

    assert any(
        "analyzer_service.py" in path
        for path in top_paths
    )


def test_retrieval_respects_top_k():
    chunks = ContextChunkingService().chunk_repository(
        REPOSITORY_ROOT
    )

    query = ContextQuery(
        query="repository analysis",
        repository_path=str(REPOSITORY_ROOT),
        top_k=3,
    )

    response = ContextRetriever().retrieve(
        chunks,
        query,
    )

    assert len(response.results) <= 3


def test_retrieval_respects_language_filter():
    chunks = ContextChunkingService().chunk_repository(
        REPOSITORY_ROOT
    )

    query = ContextQuery(
        query="repository analysis",
        repository_path=str(REPOSITORY_ROOT),
        top_k=5,
        languages=["Python"],
    )

    response = ContextRetriever().retrieve(
        chunks,
        query,
    )

    for result in response.results:
        assert result.chunk.language == "Python"