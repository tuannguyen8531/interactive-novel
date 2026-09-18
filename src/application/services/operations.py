"""Safe runtime backup and restore use cases for the local application."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path

from src.application.contracts.backups import DatabaseBackupReport, IntegrityReport
from src.application.errors import ApplicationValidationError, ResourceNotFoundError
from src.services.persistence.backup import BackupOperationError, DatabaseBackupService

_BACKUP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}\.db\.backup$")
_BACKUP_FILE = "game.db.backup"
_MAX_BACKUPS = 3


class RuntimeOperationsApplicationService:
    """Expose file-scoped operations without accepting arbitrary filesystem paths."""

    def __init__(self, database_path: Path, exports_directory: Path) -> None:
        self._service = DatabaseBackupService(database_path)
        self._exports = exports_directory.expanduser().resolve()
        self._lock = asyncio.Lock()

    async def list_backups(self) -> tuple[dict[str, object], ...]:
        self._exports.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, object]] = []
        for name, path in self._backup_entries():
            integrity = await asyncio.to_thread(self._service.integrity_check, path)
            records.append(
                {
                    "name": name,
                    "size_bytes": path.stat().st_size,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(),
                    "integrity": integrity.as_dict(),
                }
            )
        return tuple(records)

    async def create_backup(self, name: str | None = None) -> DatabaseBackupReport:
        async with self._lock:
            requested_name = name or datetime.now().astimezone().strftime("game-%Y%m%d-%H%M%S.db.backup")
            backup_name = self._unique_backup_name(requested_name)
            destination = self._new_backup_path(backup_name)
            try:
                report = await asyncio.to_thread(self._service.create_backup, destination)
                self._prune_backups()
                return report
            except BackupOperationError as error:
                raise ApplicationValidationError(str(error)) from error

    async def restore_backup(self, name: str) -> DatabaseBackupReport:
        source = self._backup_path(name)
        if not source.is_file():
            raise ResourceNotFoundError(f"Backup {name} does not exist.")
        async with self._lock:
            try:
                return await asyncio.to_thread(self._service.restore_backup, source)
            except BackupOperationError as error:
                raise ApplicationValidationError(str(error)) from error

    async def integrity_check(self) -> IntegrityReport:
        return await asyncio.to_thread(self._service.integrity_check)

    def _backup_path(self, name: str) -> Path:
        self._validate_backup_name(name)
        archive = self._exports / name
        if archive.is_dir():
            return archive / _BACKUP_FILE
        return archive

    def _new_backup_path(self, name: str) -> Path:
        return self._exports / name / _BACKUP_FILE

    def _backup_entries(self) -> tuple[tuple[str, Path], ...]:
        entries: list[tuple[str, Path]] = []
        for archive in self._exports.glob("*.db.backup"):
            path = archive / _BACKUP_FILE if archive.is_dir() else archive
            if path.is_file():
                entries.append((archive.name, path))
        return tuple(sorted(entries, key=lambda item: (item[1].stat().st_mtime_ns, item[0]), reverse=True))

    def _unique_backup_name(self, name: str) -> str:
        self._validate_backup_name(name)
        candidate = name
        index = 2
        while (self._exports / candidate).exists():
            stem = name.removesuffix(".db.backup")
            candidate = f"{stem}-{index}.db.backup"
            self._validate_backup_name(candidate)
            index += 1
        return candidate

    def _prune_backups(self) -> None:
        entries = self._backup_entries()
        for _, path in entries:
            self._remove_sidecars(path)
        for _, path in entries[_MAX_BACKUPS:]:
            if path.parent != self._exports:
                children = tuple(path.parent.iterdir())
                if len(children) != 1 or children[0] != path:
                    continue
            path.unlink()
            if path.parent != self._exports:
                path.parent.rmdir()

    @staticmethod
    def _remove_sidecars(path: Path) -> None:
        sidecar_names = {f"{path.name}{suffix}" for suffix in ("-wal", "-shm", "-journal")}
        temporary_prefix = f".{path.name}."
        for child in path.parent.iterdir():
            if child.name in sidecar_names or (
                child.name.startswith(temporary_prefix) and child.name.endswith(("-wal", "-shm", "-journal"))
            ):
                child.unlink(missing_ok=True)

    @staticmethod
    def _validate_backup_name(name: str) -> None:
        if not _BACKUP_NAME.fullmatch(name):
            raise ApplicationValidationError("Backup name must end in .db.backup and contain only safe filename characters.")


__all__ = ["RuntimeOperationsApplicationService"]
