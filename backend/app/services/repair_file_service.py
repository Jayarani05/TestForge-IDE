import hashlib
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath


@dataclass
class _RepairOperation:
    repair_id: str
    repository: Path
    target: Path
    relative_path: str
    original_code: str
    proposed_code: str
    original_digest: str
    file_mode: int
    backup_path: Path | None = None
    applied_digest: str | None = None
    status: str = "generated"


class RepairFileService:
    """Apply and restore only explicit, conflict-checked repair operations."""

    SUPPORTED_SUFFIXES = {".py", ".js", ".ts"}

    def __init__(self) -> None:
        self._operations: dict[str, _RepairOperation] = {}
        self._lock = threading.RLock()

    def _resolve_target(
        self,
        repository_path: str,
        file_path: str,
    ) -> tuple[Path, Path, str]:
        repository = Path(repository_path).expanduser().resolve()
        if not repository.is_dir():
            raise ValueError("Selected repository must be an existing directory.")
        windows_path = PureWindowsPath(file_path)
        relative = Path(file_path)
        if (
            not file_path.strip()
            or relative.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or any(part == ".." for part in file_path.replace("\\", "/").split("/"))
        ):
            raise ValueError("Repair target must be a safe repository-relative path.")
        target = (repository / relative).resolve()
        try:
            relative_path = target.relative_to(repository).as_posix()
        except ValueError as exc:
            raise ValueError("Repair target escapes the repository.") from exc
        if not target.is_file():
            raise FileNotFoundError("Repair target file does not exist.")
        if target.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError("Repair candidates are unsupported for this file type.")
        return repository, target, relative_path

    @staticmethod
    def _digest(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def register_candidate(
        self,
        repair_id: str,
        repository_path: str,
        file_path: str,
        original_code: str,
        proposed_code: str,
    ) -> None:
        repository, target, relative_path = self._resolve_target(
            repository_path,
            file_path,
        )
        current_bytes = target.read_bytes()
        try:
            current_code = current_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Repair target must be UTF-8 encoded text.") from exc
        if current_code != original_code:
            raise ValueError("Repair target changed while the candidate was generated.")
        with self._lock:
            if repair_id in self._operations:
                raise ValueError("Repair operation identifier already exists.")
            self._operations[repair_id] = _RepairOperation(
                repair_id=repair_id,
                repository=repository,
                target=target,
                relative_path=relative_path,
                original_code=original_code,
                proposed_code=proposed_code,
                original_digest=self._digest(current_bytes),
                file_mode=target.stat().st_mode,
            )

    def apply_repair(
        self,
        repair_id: str,
        approved: bool,
    ) -> tuple[str, str]:
        if not approved:
            raise ValueError("Explicit approval is required to apply a repair.")
        with self._lock:
            operation = self._get_operation(repair_id)
            if operation.status != "generated":
                raise ValueError("Repair candidate has already been applied or restored.")
            current = operation.target.read_bytes()
            if self._digest(current) != operation.original_digest:
                raise ValueError("Repair target changed after review; create a new candidate.")

            backup = operation.target.with_name(
                f"{operation.target.name}.testforge-repair-{repair_id}.backup"
            )
            backup_created = False
            try:
                backup_file = backup.open("xb")
                backup_created = True
                with backup_file:
                    backup_file.write(current)
                    backup_file.flush()
                    os.fsync(backup_file.fileno())
                proposed = operation.proposed_code.encode("utf-8")
                self._atomic_write(
                    operation.target,
                    proposed,
                    operation.file_mode,
                )
            except OSError:
                if backup_created and backup.exists():
                    backup.unlink()
                raise

            operation.backup_path = backup
            operation.applied_digest = self._digest(proposed)
            operation.status = "applied"
            return operation.target.read_text(encoding="utf-8"), operation.relative_path

    def restore_backup(self, repair_id: str) -> tuple[str, str]:
        with self._lock:
            operation = self._get_operation(repair_id)
            if operation.status != "applied" or operation.backup_path is None:
                raise ValueError("Only an applied repair can be restored.")
            current = operation.target.read_bytes()
            if self._digest(current) != operation.applied_digest:
                raise ValueError(
                    "Repair target changed after application; restoration was not applied."
                )
            backup_bytes = operation.backup_path.read_bytes()
            if self._digest(backup_bytes) != operation.original_digest:
                raise ValueError("Repair backup failed integrity validation.")
            self._atomic_write(
                operation.target,
                backup_bytes,
                operation.file_mode,
            )
            operation.status = "restored"
            operation.backup_path.unlink()
            return backup_bytes.decode("utf-8"), operation.relative_path

    def _get_operation(self, repair_id: str) -> _RepairOperation:
        operation = self._operations.get(repair_id)
        if operation is None:
            raise ValueError("Repair operation was not found or has expired.")
        return operation

    @staticmethod
    def _atomic_write(
        target: Path,
        content: bytes,
        file_mode: int,
    ) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".testforge-repair-",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.chmod(temporary, file_mode)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
