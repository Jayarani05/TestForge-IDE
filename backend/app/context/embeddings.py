from abc import ABC, abstractmethod

from app.context.models import ContextChunk


class EmbeddingProvider(ABC):
    """Interface for converting context chunks into vectors."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Convert text into an embedding vector."""
        raise NotImplementedError

    def embed_chunk(self, chunk: ContextChunk) -> list[float]:
        """Convert a context chunk into an embedding vector."""
        return self.embed_text(chunk.content)

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic local embedding provider for development/testing.

    This is NOT the production semantic embedding model.
    It allows the vector pipeline to be developed and tested
    without requiring an external API.
    """

    def __init__(self, dimension: int = 128) -> None:
        if dimension <= 0:
            raise ValueError(
                "Embedding dimension must be greater than zero."
            )

        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension

        if not text.strip():
            return vector

        tokens = text.lower().split()

        for token in tokens:
            index = hash(token) % self._dimension
            vector[index] += 1.0

        magnitude = sum(
            value * value
            for value in vector
        ) ** 0.5

        if magnitude == 0:
            return vector

        return [
            value / magnitude
            for value in vector
        ]