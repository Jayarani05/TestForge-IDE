from pathlib import Path

from app.context.chunker import ContextChunker
from app.context.models import ContextChunk
from app.repository.tree_service import RepositoryTreeService


class ContextChunkingService:
    """Create AI-readable context chunks for an entire repository."""

    IGNORED_DIRECTORIES = {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "dist-electron",
        "build",
        "coverage",
        ".nyc_output",
        "out",
        "release",
        "electron-user-data",
    }

    

    IGNORED_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".gitignore",
   }  

    IGNORED_EXTENSIONS = {
        ".pyc",
        ".pyo",
        ".log",
        ".tsbuildinfo",
    }

    def __init__(self) -> None:
        self.tree_service = RepositoryTreeService()
        self.chunker = ContextChunker()

    def chunk_repository(
        self,
        repository_path: str | Path,
    ) -> list[ContextChunk]:
        root = Path(repository_path).expanduser().resolve()

        if not root.exists():
            raise FileNotFoundError(
                "Repository path does not exist."
            )

        if not root.is_dir():
            raise ValueError(
                "Repository path must be a directory."
            )

        tree = self.tree_service.scan_repository(
            str(root)
        )

        chunks: list[ContextChunk] = []

        for file in tree.files:
            if self._should_ignore(file.relative_path):
                continue

            file_chunks = self.chunker.chunk_file(
                repository_path=root,
                file_path=file.path,
                relative_path=file.relative_path,
                language=file.language,
            )

            chunks.extend(file_chunks)

        return chunks

    def _should_ignore(
        self,
        relative_path: str,
    ) -> bool:
        path = Path(relative_path)

        if any(
            part in self.IGNORED_DIRECTORIES
            for part in path.parts
        ):
            return True

        if path.name in self.IGNORED_FILE_NAMES:
            return True

        if path.suffix.lower() in self.IGNORED_EXTENSIONS:
            return True

        return False