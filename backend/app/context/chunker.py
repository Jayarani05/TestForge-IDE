from pathlib import Path

from app.context.models import (
    ContextChunk,
    ContextSourceType,
)


class ContextChunker:
    """Convert repository files into AI-readable context chunks."""

    DEFAULT_CHUNK_LINES = 80
    DEFAULT_OVERLAP_LINES = 10

    SOURCE_TYPE_BY_LANGUAGE = {
        "Python": ContextSourceType.SOURCE_CODE,
        "TypeScript": ContextSourceType.SOURCE_CODE,
        "JavaScript": ContextSourceType.SOURCE_CODE,
        "Java": ContextSourceType.SOURCE_CODE,
        "HTML": ContextSourceType.SOURCE_CODE,
        "CSS": ContextSourceType.SOURCE_CODE,
        "JSON": ContextSourceType.CONFIGURATION,
        "YAML": ContextSourceType.CONFIGURATION,
        "XML": ContextSourceType.CONFIGURATION,
        "Markdown": ContextSourceType.DOCUMENTATION,
    }

    def chunk_file(
        self,
        repository_path: str | Path,
        file_path: str | Path,
        relative_path: str,
        language: str | None = None,
        chunk_lines: int = DEFAULT_CHUNK_LINES,
        overlap_lines: int = DEFAULT_OVERLAP_LINES,
    ) -> list[ContextChunk]:
        repository = Path(repository_path)
        path = Path(file_path)

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

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            return []

        # PostgreSQL TEXT does not allow NUL characters.
        # Remove them before creating context chunks.
        content = content.replace("\x00", "")

        if not content.strip():
            return []

        lines = content.splitlines()

        source_type = self._detect_source_type(
            relative_path=relative_path,
            language=language,
        )

        chunks: list[ContextChunk] = []

        step = chunk_lines - overlap_lines
        start_index = 0

        while start_index < len(lines):
            end_index = min(
                start_index + chunk_lines,
                len(lines),
            )

            chunk_content = "\n".join(
                lines[start_index:end_index]
            )

            if not chunk_content.strip():
                break

            chunks.append(
                ContextChunk(
                    repository_path=str(repository),
                    file_path=str(path),
                    relative_path=relative_path,
                    content=chunk_content,
                    source_type=source_type,
                    language=language,
                    start_line=start_index + 1,
                    end_line=end_index,
                    chunk_type="file_segment",
                    metadata={
                        "chunk_index": str(len(chunks)),
                    },
                )
            )

            if end_index >= len(lines):
                break

            start_index += step

        return chunks

    def _detect_source_type(
        self,
        relative_path: str,
        language: str | None,
    ) -> ContextSourceType:
        normalized_path = relative_path.lower()

        if self._is_api_specification(
            normalized_path
        ):
            return ContextSourceType.API_SPECIFICATION

        if self._is_test_file(
            normalized_path
        ):
            return ContextSourceType.TEST

        if self._is_automation_file(
            normalized_path
        ):
            return ContextSourceType.AUTOMATION

        if language in self.SOURCE_TYPE_BY_LANGUAGE:
            return self.SOURCE_TYPE_BY_LANGUAGE[
                language
            ]

        return ContextSourceType.SOURCE_CODE

    @staticmethod
    def _is_api_specification(
        path: str,
    ) -> bool:
        api_names = {
            "openapi.yaml",
            "openapi.yml",
            "openapi.json",
            "swagger.yaml",
            "swagger.yml",
            "swagger.json",
        }

        return Path(path).name.lower() in api_names

    @staticmethod
    def _is_test_file(
        path: str,
    ) -> bool:
        name = Path(path).name.lower()

        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or ".test." in name
            or ".spec." in name
        )

    @staticmethod
    def _is_automation_file(
        path: str,
    ) -> bool:
        normalized = path.lower()

        automation_keywords = (
            "playwright",
            "selenium",
            "automation",
        )

        return any(
            keyword in normalized
            for keyword in automation_keywords
        )