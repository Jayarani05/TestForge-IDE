import os
from pathlib import Path

from app.repository.file_tree import (
    RepositoryDirectory,
    RepositoryFile,
    RepositoryTree,
)


class RepositoryTreeService:
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

    LANGUAGE_MAP = {
        ".py": "Python",
        ".java": "Java",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C/C++",
        ".hpp": "C++",
        ".cs": "C#",
        ".go": "Go",
        ".rs": "Rust",
        ".php": "PHP",
        ".rb": "Ruby",
        ".kt": "Kotlin",
        ".swift": "Swift",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".json": "JSON",
        ".xml": "XML",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".md": "Markdown",
        ".sql": "SQL",
        ".sh": "Shell",
        ".bat": "Batch",
        ".ps1": "PowerShell",
    }

    SPECIAL_FILE_MAP = {
        "Dockerfile": "Docker",
        "docker-compose.yml": "Docker Compose",
        "docker-compose.yaml": "Docker Compose",
        "package.json": "Node.js",
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "pom.xml": "Maven",
        "build.gradle": "Gradle",
        "build.gradle.kts": "Gradle",
        "alembic.ini": "Alembic",
        "README": "Documentation",
        "README.md": "Documentation",
        "README.txt": "Documentation",
    }

    def scan_repository(
        self,
        repository_path: str,
    ) -> RepositoryTree:
        root = Path(repository_path).expanduser().resolve()

        if not root.exists():
            raise FileNotFoundError(
                "Repository path does not exist."
            )

        if not root.is_dir():
            raise ValueError(
                "Repository path must be a directory."
            )

        files: list[RepositoryFile] = []
        directories: list[RepositoryDirectory] = []

        for current_path, dir_names, file_names in os.walk(root):
            dir_names[:] = [
                directory
                for directory in dir_names
                if directory not in self.IGNORED_DIRECTORIES
            ]

            current = Path(current_path)

            if current != root:
                relative_directory = current.relative_to(root)

                directories.append(
                    RepositoryDirectory(
                        name=current.name,
                        path=str(current),
                        relative_path=str(relative_directory),
                    )
                )

            for file_name in file_names:
                file_path = current / file_name

                try:
                    size_bytes = file_path.stat().st_size
                except OSError:
                    continue

                relative_file = file_path.relative_to(root)
                extension = file_path.suffix.lower() or None

                language = self._detect_language(
                    file_name,
                    extension,
                )

                files.append(
                    RepositoryFile(
                        name=file_name,
                        path=str(file_path),
                        relative_path=str(relative_file),
                        extension=extension,
                        language=language,
                        size_bytes=size_bytes,
                    )
                )

        return RepositoryTree(
            repository_path=str(root),
            files=files,
            directories=directories,
        )

    def _detect_language(
        self,
        file_name: str,
        extension: str | None,
    ) -> str | None:
        special_file_type = self.SPECIAL_FILE_MAP.get(
            file_name
        )

        if special_file_type is not None:
            return special_file_type

        if extension is None:
            return None

        return self.LANGUAGE_MAP.get(extension)
