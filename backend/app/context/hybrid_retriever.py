from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.context.models import (
    ContextChunk,
    ContextQuery,
    ContextResponse,
    ContextResult,
    ContextSourceType,
)
from app.context.persistent_retriever import (
    PersistentContextRetriever,
)
from app.context.retriever import ContextRetriever
from app.models.context_embedding import ContextEmbedding


class HybridContextRetriever:
    """
    Combine lexical and vector retrieval.

    Lexical retrieval helps with exact repository terminology,
    filenames, symbols, and implementation-specific terms.

    Vector retrieval helps identify relevant context based on
    embedding similarity.
    """

    LEXICAL_WEIGHT = 0.4
    VECTOR_WEIGHT = 0.6

    def __init__(
        self,
        vector_retriever: PersistentContextRetriever,
    ) -> None:
        self.lexical_retriever = ContextRetriever()
        self.vector_retriever = vector_retriever

    async def retrieve(
        self,
        session: AsyncSession,
        query: ContextQuery,
    ) -> ContextResponse:
        """
        Retrieve repository context using both lexical
        and vector-based retrieval.
        """

        chunks = await self._load_chunks(
            session=session,
            repository_path=query.repository_path,
        )

        lexical_response = (
            self.lexical_retriever.retrieve(
                chunks=chunks,
                query=query,
            )
        )

        vector_response = (
            await self.vector_retriever.retrieve(
                session=session,
                query=query,
            )
        )

        combined_scores: dict[
            str,
            dict[str, object],
        ] = {}

        # ---------------------------------------------------------
        # Lexical results
        # ---------------------------------------------------------

        for result in lexical_response.results:
            key = self._chunk_key(result)

            combined_scores[key] = {
                "chunk": result.chunk,
                "lexical_score": result.score,
                "vector_score": 0.0,
            }

        # ---------------------------------------------------------
        # Vector results
        # ---------------------------------------------------------

        for result in vector_response.results:
            key = self._chunk_key(result)

            if key not in combined_scores:
                combined_scores[key] = {
                    "chunk": result.chunk,
                    "lexical_score": 0.0,
                    "vector_score": result.score,
                }
            else:
                combined_scores[key][
                    "vector_score"
                ] = result.score

        # ---------------------------------------------------------
        # Hybrid scoring
        # ---------------------------------------------------------

        results: list[ContextResult] = []

        for item in combined_scores.values():
            chunk = item["chunk"]

            lexical_score = float(
                item["lexical_score"]
            )

            vector_score = float(
                item["vector_score"]
            )

            hybrid_score = (
                self.LEXICAL_WEIGHT
                * lexical_score
                + self.VECTOR_WEIGHT
                * vector_score
            )

            if hybrid_score <= 0:
                continue

            results.append(
                ContextResult(
                    chunk=chunk,
                    score=min(
                        hybrid_score,
                        1.0,
                    ),
                )
            )

        # ---------------------------------------------------------
        # Sort by hybrid score
        # ---------------------------------------------------------

        results.sort(
            key=lambda result: (
                result.score,
                result.chunk.relative_path,
                result.chunk.start_line or 0,
            ),
            reverse=True,
        )

        selected_results = results[:query.top_k]

        return ContextResponse(
            query=query.query,
            repository_path=query.repository_path,
            results=selected_results,
            total_results=len(results),
        )

    async def _load_chunks(
        self,
        session: AsyncSession,
        repository_path: str,
    ) -> list[ContextChunk]:
        """
        Load persisted context chunks from PostgreSQL.
        """

        statement = (
            select(ContextEmbedding)
            .where(
                ContextEmbedding.repository_path
                == repository_path
            )
        )

        result = await session.execute(statement)

        records = result.scalars().all()

        chunks: list[ContextChunk] = []

        for record in records:
            chunks.append(
                ContextChunk(
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
            )

        return chunks

    @staticmethod
    def _chunk_key(
        result: ContextResult,
    ) -> str:
        """
        Create a stable identifier for a context chunk.
        """

        chunk = result.chunk

        return "|".join(
            [
                chunk.repository_path,
                chunk.relative_path,
                str(chunk.start_line),
                str(chunk.end_line),
            ]
        )