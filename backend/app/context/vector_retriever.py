from app.context.embeddings import EmbeddingProvider
from app.context.models import (
    ContextChunk,
    ContextQuery,
    ContextResponse,
    ContextResult,
)
from app.context.vector import cosine_similarity


class VectorRetriever:
    """Retrieve repository context using embedding similarity."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.embedding_provider = embedding_provider

    def retrieve(
        self,
        chunks: list[ContextChunk],
        query: ContextQuery,
    ) -> ContextResponse:
        query_vector = (
            self.embedding_provider.embed_text(
                query.query
            )
        )

        candidates: list[ContextResult] = []

        for chunk in chunks:
            if chunk.repository_path != query.repository_path:
                continue

            if query.source_types:
                if chunk.source_type not in query.source_types:
                    continue

            if query.languages:
                if chunk.language not in query.languages:
                    continue

            chunk_vector = (
                self.embedding_provider.embed_chunk(chunk)
            )

            score = cosine_similarity(
                query_vector,
                chunk_vector,
            )

            if score <= 0:
                continue

            candidates.append(
                ContextResult(
                    chunk=chunk,
                    score=score,
                )
            )

        candidates.sort(
            key=lambda result: result.score,
            reverse=True,
        )

        results = candidates[: query.top_k]

        return ContextResponse(
            query=query.query,
            repository_path=query.repository_path,
            results=results,
            total_results=len(candidates),
        )