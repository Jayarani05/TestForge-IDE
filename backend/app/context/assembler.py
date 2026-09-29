from app.context.models import (
    ContextAssembly,
    ContextChunk,
    ContextResult,
)


class ContextAssembler:
    """
    Assemble retrieved repository chunks into
    an LLM-ready context package.
    """

    DEFAULT_MAX_CHUNKS = 10
    DEFAULT_MAX_CHARACTERS = 30000

    def assemble(
        self,
        query: str,
        repository_path: str,
        results: list[ContextResult],
        max_chunks: int = DEFAULT_MAX_CHUNKS,
        max_characters: int = DEFAULT_MAX_CHARACTERS,
    ) -> ContextAssembly:
        """
        Build a context window from retrieved chunks.
        """

        if max_chunks <= 0:
            raise ValueError(
                "max_chunks must be greater than zero."
            )

        if max_characters <= 0:
            raise ValueError(
                "max_characters must be greater than zero."
            )

        selected_chunks: list[ContextChunk] = []

        current_characters = 0

        for result in results:
            if len(selected_chunks) >= max_chunks:
                break

            chunk = result.chunk

            chunk_size = len(chunk.content)

            if (
                current_characters + chunk_size
                > max_characters
            ):
                remaining = (
                    max_characters
                    - current_characters
                )

                if remaining <= 0:
                    break

                truncated_content = (
                    chunk.content[:remaining]
                )

                if not truncated_content.strip():
                    break

                chunk = chunk.model_copy(
                    update={
                        "content": truncated_content,
                    }
                )

                selected_chunks.append(chunk)

                current_characters += len(
                    truncated_content
                )

                break

            selected_chunks.append(chunk)

            current_characters += chunk_size

        estimated_tokens = self._estimate_tokens(
            selected_chunks
        )

        return ContextAssembly(
            query=query,
            repository_path=repository_path,
            chunks=selected_chunks,
            total_chunks=len(selected_chunks),
            estimated_tokens=estimated_tokens,
        )

    @staticmethod
    def _estimate_tokens(
        chunks: list[ContextChunk],
    ) -> int:
        """
        Estimate token count using a simple
        character-based approximation.

        Approximately four characters are treated
        as one token.
        """

        total_characters = sum(
            len(chunk.content)
            for chunk in chunks
        )

        return max(
            1,
            total_characters // 4,
        )