from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ContextEmbedding(Base):
    __tablename__ = "context_embeddings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    repository_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    relative_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    language: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    start_line: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    end_line: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    chunk_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    embedding: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )