from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context.embeddings import EmbeddingProvider
from app.context.models import ContextChunk
from app.models.context_embedding import ContextEmbedding


class ContextEmbeddingService:
    """Persist and retrieve repository context embeddings."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.embedding_provider = embedding_provider

    async def index_chunks(
        self,
        session: AsyncSession,
        chunks: list[ContextChunk],
    ) -> int:
        """Create embeddings and persist context chunks."""

        if not chunks:
            return 0

        repository_paths = {
            chunk.repository_path
            for chunk in chunks
        }

        for repository_path in repository_paths:
            await session.execute(
                delete(ContextEmbedding).where(
                    ContextEmbedding.repository_path
                    == repository_path
                )
            )

        records: list[ContextEmbedding] = []

        for chunk in chunks:
            embedding = self.embedding_provider.embed_chunk(
                chunk
            )

            record = ContextEmbedding(
                repository_path=chunk.repository_path,
                file_path=chunk.file_path,
                relative_path=chunk.relative_path,
                content=chunk.content,
                source_type=chunk.source_type.value,
                language=chunk.language,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                chunk_type=chunk.chunk_type,
                embedding_dimension=len(embedding),
                embedding=self._serialize_embedding(
                    embedding
                ),
            )

            records.append(record)

        session.add_all(records)

        await session.commit()

        return len(records)

    async def get_chunks(
        self,
        session: AsyncSession,
        repository_path: str,
    ) -> list[ContextChunk]:
        """Load persisted context chunks for a repository."""

        result = await session.execute(
            select(ContextEmbedding)
            .where(
                ContextEmbedding.repository_path
                == repository_path
            )
            .order_by(
                ContextEmbedding.relative_path,
                ContextEmbedding.start_line,
            )
        )

        records = result.scalars().all()

        return [
            self._to_context_chunk(record)
            for record in records
        ]

    @staticmethod
    def _serialize_embedding(
        embedding: list[float],
    ) -> str:
        return ",".join(
            str(value)
            for value in embedding
        )

    @staticmethod
    def _to_context_chunk(
        record: ContextEmbedding,
    ) -> ContextChunk:
        from app.context.models import ContextSourceType

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