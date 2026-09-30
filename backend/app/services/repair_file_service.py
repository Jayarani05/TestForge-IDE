from pathlib import Path
import shutil


class RepairFileService:

    def _resolve_target(
        self,
        repository_path: str,
        file_path: str,
    ) -> tuple[Path, Path]:

        repository = Path(repository_path).resolve()
        target = (repository / file_path).resolve()

        try:
            target.relative_to(repository)
        except ValueError as exc:
            raise ValueError(
                "Repair target escapes the repository."
            ) from exc

        if not target.exists():
            raise FileNotFoundError(
                f"Repair target does not exist: {file_path}"
            )

        if not target.is_file():
            raise ValueError(
                f"Repair target is not a file: {file_path}"
            )

        return repository, target

    def create_backup(
        self,
        repository_path: str,
        file_path: str,
    ) -> Path:

        _, target = self._resolve_target(
            repository_path,
            file_path,
        )

        backup = target.with_suffix(
            target.suffix + ".testforge-backup"
        )

        shutil.copy2(target, backup)

        return backup

    def apply_repair(
        self,
        repository_path: str,
        file_path: str,
        repaired_code: str,
    ) -> str:

        _, target = self._resolve_target(
            repository_path,
            file_path,
        )

        target.write_text(
            repaired_code,
            encoding="utf-8",
        )

        return str(target)

    def restore_backup(
        self,
        repository_path: str,
        file_path: str,
    ) -> str:

        _, target = self._resolve_target(
            repository_path,
            file_path,
        )

        backup = target.with_suffix(
            target.suffix + ".testforge-backup"
        )

        if not backup.exists():
            raise FileNotFoundError(
                f"Backup does not exist: {backup}"
            )

        shutil.copy2(backup, target)
        backup.unlink()

        return str(target)

    def remove_backup(
        self,
        repository_path: str,
        file_path: str,
    ) -> None:

        _, target = self._resolve_target(
            repository_path,
            file_path,
        )

        backup = target.with_suffix(
            target.suffix + ".testforge-backup"
        )

        if backup.exists():
            backup.unlink()