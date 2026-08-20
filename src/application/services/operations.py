"""Safe runtime backup and restore use cases for the local application."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path

from src.application.contracts.backups import DatabaseBackupReport, IntegrityReport
from src.application.errors import ApplicationValidationError, ResourceNotFoundError
from src.services.persistence.backup import BackupOperationError, DatabaseBackupService

_BACKUP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}\.db\.backup$")


class RuntimeOperationsApplicationService:
    """Expose file-scoped operations without accepting arbitrary filesystem paths."""

    def __init__(self, database_path: Path, exports_directory: Path) -> None:
        self._service = DatabaseBackupService(database_path)
        self._exports = exports_directory.expanduser().resolve()
        self._lock = asyncio.Lock()

    async def list_backups(self) -> tuple[dict[str, object], ...]:
        self._exports.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, object]] = []
        for path in sorted(self._exports.glob("*.db.backup"), key=lambda item: item.stat().st_mtime, reverse=True):
            integrity = await asyncio.to_thread(self._service.integrity_check, path)
            records.append(
                {
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                    "integrity": integrity.as_dict(),
                }
            )
        return tuple(records)

    async def create_backup(self, name: str | None = None) -> DatabaseBackupReport:
        destination = self._backup_path(name or datetime.now(UTC).strftime("game-%Y%m%d-%H%M%S.db.backup"))
        async with self._lock:
            try:
                return await asyncio.to_thread(self._service.create_backup, destination)
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
        if not _BACKUP_NAME.fullmatch(name):
            raise ApplicationValidationError("Backup name must end in .db.backup and contain only safe filename characters.")
        return self._exports / name


__all__ = ["RuntimeOperationsApplicationService"]
