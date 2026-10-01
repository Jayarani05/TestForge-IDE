from pathlib import Path

from app.context.models import ContextChunk, ContextSourceType


class ContextChunker:
    """
    Convert repository files into repository-aware context chunks.

    The chunker intentionally ignores binary/generated assets so that
    images, archives, executables, databases, and other non-text files
    never enter the LLM context or PostgreSQL text columns.
    """

    DEFAULT_CHUNK_LINES = 80
    DEFAULT_OVERLAP_LINES = 10

    IGNORED_EXTENSIONS = {
        # Images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
        ".ico",
        ".svg",

        # Documents / packaged binary formats
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",

        # Archives
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",

        # Compiled / executable files
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".obj",
        ".o",
        ".a",
        ".lib",
        ".class",
        ".pyc",
        ".pyo",

        # Database / binary data
        ".db",
        ".sqlite",
        ".sqlite3",
        ".mdb",

        # Fonts
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",

        # Media
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",

        # Other binary / generated assets
        ".wasm",
        ".map",
        ".lockb",
    }

    IGNORED_FILENAMES = {
        ".ds_store",
        "thumbs.db",
        "desktop.ini",
    }

    SOURCE_EXTENSION_MAP = {
        # Python
        ".py": "Python",
        ".pyw": "Python",

        # JavaScript / TypeScript
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",

        # JVM
        ".java": "Java",
        ".kt": "Kotlin",
        ".kts": "Kotlin",

        # C / C++
        ".c": "C",
        ".h": "C",
        ".cpp": "C++",
        ".cc": "C++",
        ".cxx": "C++",
        ".hpp": "C++",

        # Other languages
        ".cs": "C#",
        ".go": "Go",
        ".rs": "Rust",
        ".php": "PHP",
        ".rb": "Ruby",
        ".swift": "Swift",
        ".dart": "Dart",
        ".scala": "Scala",

        # Shell
        ".sh": "Shell",
        ".bash": "Shell",
        ".zsh": "Shell",
        ".ps1": "PowerShell",
        ".bat": "Batch",
        ".cmd": "Batch",

        # Web
        ".html": "HTML",
        ".htm": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".sass": "Sass",
        ".less": "Less",

        # Data / configuration
        ".json": "JSON",
        ".jsonc": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".xml": "XML",
        ".toml": "TOML",
        ".ini": "INI",
        ".cfg": "Configuration",
        ".conf": "Configuration",
        ".env": "Environment",

        # Documentation
        ".md": "Markdown",
        ".mdx": "Markdown",
        ".txt": "Text",
        ".rst": "reStructuredText",
        ".adoc": "AsciiDoc",
    }

    def __init__(
        self,
        chunk_lines: int = DEFAULT_CHUNK_LINES,
        overlap_lines: int = DEFAULT_OVERLAP_LINES,
    ):
        if chunk_lines <= 0:
            raise ValueError(
                "chunk_lines must be greater than zero."
            )

        if overlap_lines < 0:
            raise ValueError(
                "overlap_lines cannot be negative."
            )

        if overlap_lines >= chunk_lines:
            raise ValueError(
                "overlap_lines must be smaller than chunk_lines."
            )

        self.chunk_lines = chunk_lines
        self.overlap_lines = overlap_lines

    @classmethod
    def should_skip_file(
        cls,
        path: str | Path,
    ) -> bool:
        """
        Return True when a file should never be read into context.
        """

        file_path = Path(path)

        name = file_path.name.lower()
        extension = file_path.suffix.lower()

        if name in cls.IGNORED_FILENAMES:
            return True

        if extension in cls.IGNORED_EXTENSIONS:
            return True

        return False

    @staticmethod
    def _looks_binary(
        content: bytes,
    ) -> bool:
        """
        Detect binary content for files whose extension is unknown.

        NUL bytes are treated as a strong binary indicator.
        """

        if not content:
            return False

        sample = content[:8192]

        if b"\x00" in sample:
            return True

        suspicious = 0

        for byte in sample:
            if byte in (9, 10, 13):
                continue

            if byte < 32:
                suspicious += 1

        return suspicious / len(sample) > 0.10

    @classmethod
    def _read_text_file(
        cls,
        path: Path,
    ) -> str | None:
        """
        Safely read a repository file as text.

        Returns None for binary or unreadable files.
        """

        try:
            raw = path.read_bytes()
        except (OSError, PermissionError):
            return None

        if cls._looks_binary(raw):
            return None

        encodings = (
            "utf-8",
            "utf-8-sig",
            "utf-16",
            "utf-16-le",
            "utf-16-be",
            "latin-1",
        )

        for encoding in encodings:
            try:
                text = raw.decode(encoding)

                if "\x00" in text:
                    return None

                return (
                    text
                    .replace("\r\n", "\n")
                    .replace("\r", "\n")
                )

            except UnicodeDecodeError:
                continue

        return None

    @staticmethod
    def _source_type(
        path: str,
    ) -> ContextSourceType:
        """
        Determine the semantic role of a repository file.
        """

        normalized = path.replace(
            "\\",
            "/",
        ).lower()

        name = Path(path).name.lower()
        extension = Path(path).suffix.lower()

        # Tests
        if (
            name.startswith("test_")
            or name.endswith("_test.py")
            or ".test." in name
            or ".spec." in name
            or "/tests/" in normalized
            or "/test/" in normalized
        ):
            return ContextSourceType.TEST

        # Automation
        if (
            "automation" in normalized
            or "playwright" in normalized
            or "selenium" in normalized
            or "cypress" in normalized
            or "/e2e/" in normalized
            or "/end-to-end/" in normalized
        ):
            return ContextSourceType.AUTOMATION

        # Documentation
        if extension in {
            ".md",
            ".mdx",
            ".txt",
            ".rst",
            ".adoc",
        }:
            return ContextSourceType.DOCUMENTATION

        # Explicit API specifications
        if name in {
            "openapi.yaml",
            "openapi.yml",
            "openapi.json",
            "swagger.yaml",
            "swagger.yml",
            "swagger.json",
        }:
            return ContextSourceType.API_SPECIFICATION

        # Configuration
        if (
            name.startswith(".env")
            or name in {
                "dockerfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                "compose.yml",
                "compose.yaml",
                "requirements.txt",
                "pyproject.toml",
                "package.json",
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "pom.xml",
                "build.gradle",
                "build.gradle.kts",
                "settings.gradle",
                "settings.gradle.kts",
            }
            or extension in {
                ".ini",
                ".cfg",
                ".conf",
                ".toml",
            }
        ):
            return ContextSourceType.CONFIGURATION

        # API-related JSON/YAML/XML
        if (
            extension in {
                ".json",
                ".yaml",
                ".yml",
                ".xml",
            }
            and (
                "api" in name
                or "swagger" in name
                or "openapi" in name
            )
        ):
            return ContextSourceType.API_SPECIFICATION

        return ContextSourceType.SOURCE_CODE

    @staticmethod
    def _language(
        path: str,
    ) -> str | None:
        file_path = Path(path)

        extension = file_path.suffix.lower()

        if extension:
            return ContextChunker.SOURCE_EXTENSION_MAP.get(
                extension,
                extension.lstrip(".").upper(),
            )

        name = file_path.name.lower()

        if name == "dockerfile":
            return "Dockerfile"

        if name.startswith(".env"):
            return "Environment"

        if name == "makefile":
            return "Makefile"

        return None

    @staticmethod
    def _is_test_file(
        path: str,
    ) -> bool:
        name = Path(path).name.lower()

        normalized = path.replace(
            "\\",
            "/",
        ).lower()

        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or ".test." in name
            or ".spec." in name
            or "/tests/" in normalized
            or "/test/" in normalized
        )

    @staticmethod
    def _is_automation_file(
        path: str,
    ) -> bool:
        normalized = path.replace(
            "\\",
            "/",
        ).lower()

        automation_keywords = (
            "selenium",
            "playwright",
            "cypress",
            "webdriver",
            "automation",
            "e2e",
            "end-to-end",
        )

        return any(
            keyword in normalized
            for keyword in automation_keywords
        )

    @classmethod
    def _chunk_type(
        cls,
        path: str,
    ) -> str:
        if cls._is_test_file(path):
            return "test"

        if cls._is_automation_file(path):
            return "automation"

        source_type = cls._source_type(path)

        if source_type == ContextSourceType.DOCUMENTATION:
            return "documentation"

        if source_type == ContextSourceType.CONFIGURATION:
            return "configuration"

        if source_type == ContextSourceType.API_SPECIFICATION:
            return "api_specification"

        return "file_segment"

    def chunk_file(
        self,
        repository_path: str,
        file_path: str,
        relative_path: str | None = None,
        language: str | None = None,
        source_type: ContextSourceType | None = None,
        chunk_type: str | None = None,
    ) -> list[ContextChunk]:
        """
        Read and chunk a single repository file.

        Optional metadata parameters allow compatibility with
        ContextChunkingService.
        """

        path = Path(file_path)

        # Never process known binary files.
        if self.should_skip_file(path):
            return []

        if not path.is_file():
            return []

        content = self._read_text_file(path)

        if content is None:
            return []

        lines = content.splitlines()

        if not lines:
            return []

        # Use caller-provided relative path when available.
        if relative_path is None:
            try:
                relative_path = str(
                    path.relative_to(
                        Path(repository_path)
                    )
                )
            except ValueError:
                relative_path = path.name

        relative_path = relative_path.replace(
            "\\",
            "/",
        )

        # Use caller-provided metadata when available.
        resolved_source_type = (
            source_type
            if source_type is not None
            else self._source_type(str(path))
        )

        resolved_language = (
            language
            if language is not None
            else self._language(str(path))
        )

        resolved_chunk_type = (
            chunk_type
            if chunk_type is not None
            else self._chunk_type(str(path))
        )

        chunks: list[ContextChunk] = []

        start_index = 0

        step = (
            self.chunk_lines
            - self.overlap_lines
        )

        while start_index < len(lines):
            end_index = min(
                start_index + self.chunk_lines,
                len(lines),
            )

            chunk_content = "\n".join(
                lines[start_index:end_index]
            )

            if chunk_content.strip():
                chunks.append(
                    ContextChunk(
                        repository_path=str(
                            repository_path
                        ),
                        file_path=str(path),
                        relative_path=relative_path,
                        content=chunk_content.replace(
                            "\x00",
                            "",
                        ),
                        source_type=resolved_source_type,
                        language=resolved_language,
                        start_line=start_index + 1,
                        end_line=end_index,
                        chunk_type=resolved_chunk_type,
                        metadata={
                            "file_name": path.name,
                            "extension": path.suffix.lower(),
                            "is_test": str(
                                self._is_test_file(
                                    str(path)
                                )
                            ),
                            "is_automation": str(
                                self._is_automation_file(
                                    str(path)
                                )
                            ),
                        },
                    )
                )

            if end_index >= len(lines):
                break

            start_index += step

        return chunks

    def chunk_repository(
        self,
        repository_path: str,
    ) -> list[ContextChunk]:
        """
        Scan the repository and produce text-only context chunks.
        """

        root = Path(repository_path)

        if not root.exists():
            raise FileNotFoundError(
                f"Repository does not exist: {repository_path}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Repository path is not a directory: {repository_path}"
            )

        ignored_directories = {
            ".git",
            ".hg",
            ".svn",
            ".venv",
            "venv",
            "env",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            "coverage",
            ".next",
            ".nuxt",
            ".cache",
            "target",
            "bin",
            "obj",
        }

        chunks: list[ContextChunk] = []

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            relative_parts = {
                part.lower()
                for part in path.relative_to(root).parts
            }

            if relative_parts.intersection(
                ignored_directories
            ):
                continue

            if self.should_skip_file(path):
                continue

            relative_path = str(
                path.relative_to(root)
            ).replace(
                "\\",
                "/",
            )

            file_chunks = self.chunk_file(
                repository_path=str(root),
                file_path=str(path),
                relative_path=relative_path,
                language=self._language(str(path)),
                source_type=self._source_type(str(path)),
                chunk_type=self._chunk_type(str(path)),
            )

            chunks.extend(file_chunks)

        return chunks


context_chunker = ContextChunker()