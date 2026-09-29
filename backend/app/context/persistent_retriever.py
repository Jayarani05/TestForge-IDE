from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context.embeddings import EmbeddingProvider
from app.context.models import (
    ContextChunk,
    ContextQuery,
    ContextResponse,
    ContextResult,
    ContextSourceType,
)
from app.context.vector import cosine_similarity
from app.models.context_embedding import ContextEmbedding


class PersistentContextRetriever:
    """Retrieve persisted repository context using embeddings."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.embedding_provider = embedding_provider

    async def retrieve(
        self,
        session: AsyncSession,
        query: ContextQuery,
    ) -> ContextResponse:
        query_vector = (
            self.embedding_provider.embed_text(
                query.query
            )
        )

        statement = (
            select(ContextEmbedding)
            .where(
                ContextEmbedding.repository_path
                == query.repository_path
            )
        )

        if query.source_types:
            statement = statement.where(
                ContextEmbedding.source_type.in_(
                    source_type.value
                    for source_type in query.source_types
                )
            )

        if query.languages:
            statement = statement.where(
                ContextEmbedding.language.in_(
                    query.languages
                )
            )

        result = await session.execute(statement)

        records = result.scalars().all()

        candidates: list[ContextResult] = []

        for record in records:
            embedding = self._deserialize_embedding(
                record.embedding
            )

            score = cosine_similarity(
                query_vector,
                embedding,
            )

            if score <= 0:
                continue

            chunk = self._to_context_chunk(record)

            candidates.append(
                ContextResult(
                    chunk=chunk,
                    score=min(score, 1.0),
                )
            )

        candidates.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        results = candidates[: query.top_k]

        return ContextResponse(
            query=query.query,
            repository_path=query.repository_path,
            results=results,
            total_results=len(candidates),
        )

    @staticmethod
    def _deserialize_embedding(
        value: str,
    ) -> list[float]:
        if not value:
            return []

        return [
            float(item)
            for item in value.split(",")
            if item.strip()
        ]

    @staticmethod
    def _to_context_chunk(
        record: ContextEmbedding,
    ) -> ContextChunk:
        return ContextChunk(
            repository_path=record.repository_path,
            file_path=record.file_path,
            relative_path=record.relative_path,
            content=record.content,
            source_type=ContextSourceType(
                record.source_type
            ),
            language=record.language,
            start_line=record.start_line,
            end_line=record.end_line,
            chunk_type=record.chunk_type,
        )