from pathlib import Path

from app.agents.test_code_generation import GeneratedTestCode


class GeneratedFileService:
    """Safely writes AI-generated test files inside a repository."""

    def save(
        self,
        repository_path: str,
        generated_file: GeneratedTestCode,
    ) -> str:
        repository = Path(repository_path).resolve()

        relative_file = Path(generated_file.file_path)

        if relative_file.is_absolute():
            raise ValueError(
                "Generated file path must be relative to the repository."
            )

        target = (repository / relative_file).resolve()

        try:
            target.relative_to(repository)
        except ValueError as exc:
            raise ValueError(
                "Generated file path escapes the repository."
            ) from exc

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        target.write_text(
            generated_file.code,
            encoding="utf-8",
        )

        return str(target)