import re
from pathlib import Path, PureWindowsPath

from app.agents.test_code_generation import GeneratedTestCode


class GeneratedFileService:
    """Safely writes AI-generated test files inside a repository."""

    WINDOWS_RESERVED_NAMES = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }

    def save(
        self,
        repository_path: str,
        generated_file: GeneratedTestCode,
        overwrite: bool = False,
    ) -> str:
        repository = Path(repository_path).expanduser().resolve()
        if not repository.is_dir():
            raise ValueError("Repository path must be an existing directory.")

        relative_path = generated_file.file_path
        windows_path = PureWindowsPath(relative_path)
        if (
            not relative_path.strip()
            or Path(relative_path).is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
        ):
            raise ValueError(
                "Generated file path must be relative to the repository."
            )

        path_parts = re.split(r"[\\/]", relative_path)
        if any(part in {"", ".", ".."} for part in path_parts):
            raise ValueError(
                "Generated file path contains an invalid or traversal component."
            )
        for part in path_parts:
            stem = part.split(".", 1)[0].upper()
            if (
                any(ord(char) < 32 for char in part)
                or any(char in '<>:"|?*' for char in part)
                or part.endswith((" ", "."))
                or stem in self.WINDOWS_RESERVED_NAMES
            ):
                raise ValueError("Generated file name is invalid.")

        target = repository.joinpath(*path_parts).resolve()
        self._ensure_within_repository(target, repository)

        if target.parent.exists() and not target.parent.is_dir():
            raise NotADirectoryError(
                "Generated file parent path is not a directory."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target = target.resolve()
        self._ensure_within_repository(target, repository)

        if overwrite:
            target.write_text(generated_file.code, encoding="utf-8")
        else:
            with target.open("x", encoding="utf-8") as generated:
                generated.write(generated_file.code)

        return str(target)

    @staticmethod
    def _ensure_within_repository(
        target: Path,
        repository: Path,
    ) -> None:
        try:
            target.relative_to(repository)
        except ValueError as exc:
            raise ValueError(
                "Generated file path escapes the repository."
            ) from exc
