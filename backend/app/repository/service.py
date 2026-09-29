import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository
from app.repository.schemas import RepositoryInfo


class RepositoryService:
    IGNORED_DIRECTORIES = {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".idea",
        ".vscode",
        "dist",
        "build",
        "coverage",
        ".next",
        ".nuxt",
        "target",
        "out",
        "bin",
        "obj",
    }

    def inspect_repository(
        self,
        repository_path: str,
    ) -> RepositoryInfo:
        path = self._validate_repository_path(repository_path)

        file_count = 0
        directory_count = 0

        for current_path, directories, files in os.walk(path):
            directories[:] = [
                directory
                for directory in directories
                if directory not in self.IGNORED_DIRECTORIES
            ]

            directory_count += len(directories)
            file_count += len(files)

        return RepositoryInfo(
            name=path.name,
            path=str(path),
            repository_type=self._detect_repository_type(path),
            file_count=file_count,
            directory_count=directory_count,
        )

    async def save_repository(
        self,
        session: AsyncSession,
        repository_info: RepositoryInfo,
    ) -> Repository:
        result = await session.execute(
            select(Repository).where(
                Repository.path == repository_info.path
            )
        )

        repository = result.scalar_one_or_none()

        if repository is None:
            repository = Repository(
                name=repository_info.name,
                path=repository_info.path,
                repository_type=repository_info.repository_type,
                file_count=repository_info.file_count,
                directory_count=repository_info.directory_count,
            )

            session.add(repository)

        else:
            repository.name = repository_info.name
            repository.repository_type = repository_info.repository_type
            repository.file_count = repository_info.file_count
            repository.directory_count = repository_info.directory_count

        await session.commit()
        await session.refresh(repository)

        return repository

    def _validate_repository_path(
        self,
        repository_path: str,
    ) -> Path:
        path = Path(repository_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(
                "Repository path does not exist."
            )

        if not path.is_dir():
            raise ValueError(
                "Repository path must be a directory."
            )

        return path

    def _detect_repository_type(
        self,
        path: Path,
    ) -> str:
        if (path / ".git").exists():
            return "git"

        if (path / "package.json").exists():
            return "node"

        if (path / "pom.xml").exists():
            return "java-maven"

        if (path / "build.gradle").exists():
            return "java-gradle"

        if (path / "build.gradle.kts").exists():
            return "java-gradle"

        if (path / "requirements.txt").exists():
            return "python"

        if (path / "pyproject.toml").exists():
            return "python"

        return "unknown"
