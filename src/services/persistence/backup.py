"""SQLite backup, restore and integrity operations.

The service uses SQLite's online backup API instead of copying a WAL database
file directly.  This keeps committed pages and WAL frames together while
preserving the canonical/derived database boundary.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from src.application.contracts.backups import DatabaseBackupReport, IntegrityReport


class BackupOperationError(RuntimeError):
    """A backup operation could not be completed safely."""


class DatabaseBackupService:
    """Perform explicit, file-scoped database backup and restore operations."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.expanduser().resolve()

    def integrity_check(self, path: Path | None = None) -> IntegrityReport:
        """Run SQLite's full integrity check without creating a missing file."""
        candidate = (path or self.database_path).expanduser().resolve()
        if not candidate.is_file():
            return IntegrityReport(str(candidate), False, "database file does not exist")
        try:
            with sqlite3.connect(_read_only_uri(candidate), uri=True) as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as error:
            return IntegrityReport(str(candidate), False, f"integrity check failed: {type(error).__name__}")
        message = str(row[0]) if row else "no integrity result"
        return IntegrityReport(str(candidate), message.lower() == "ok", message)

    def create_backup(self, destination: Path) -> DatabaseBackupReport:
        """Create and verify an atomic SQLite backup at an explicit destination."""
        source = self._source_file()
        destination = destination.expanduser().resolve()
        self._ensure_distinct(source, destination)
        source_integrity = self.integrity_check(source)
        if not source_integrity.ok:
            raise BackupOperationError(f"source database is not healthy: {source_integrity.message}")
        self._copy_database(source, destination)
        return self._report(source, destination)

    def restore_backup(self, source: Path, destination: Path | None = None) -> DatabaseBackupReport:
        """Verify a backup and atomically restore it to the requested database path."""
        source = source.expanduser().resolve()
        destination = (destination or self.database_path).expanduser().resolve()
        if not source.is_file():
            raise BackupOperationError(f"backup file does not exist: {source}")
        self._ensure_distinct(source, destination)
        source_integrity = self.integrity_check(source)
        if not source_integrity.ok:
            raise BackupOperationError(f"backup database is not healthy: {source_integrity.message}")
        self._copy_database(source, destination)
        return self._report(source, destination)

    def _source_file(self) -> Path:
        if not self.database_path.is_file():
            raise BackupOperationError(f"source database does not exist: {self.database_path}")
        return self.database_path

    @staticmethod
    def _ensure_distinct(source: Path, destination: Path) -> None:
        if source == destination:
            raise BackupOperationError("source and destination database paths must differ")
        destination.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _copy_database(source: Path, destination: Path) -> None:
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            with sqlite3.connect(source) as source_connection, sqlite3.connect(temporary) as target_connection:
                source_connection.backup(target_connection)
                target_connection.execute("PRAGMA wal_checkpoint(FULL)")
            os.replace(temporary, destination)
        except sqlite3.DatabaseError as error:
            raise BackupOperationError(f"SQLite backup failed: {type(error).__name__}") from error
        finally:
            if temporary.exists():
                temporary.unlink()

    def _report(self, source: Path, destination: Path) -> DatabaseBackupReport:
        integrity = self.integrity_check(destination)
        if not integrity.ok:
            raise BackupOperationError(f"destination database is not healthy: {integrity.message}")
        return DatabaseBackupReport(
            source_path=str(source),
            destination_path=str(destination),
            size_bytes=destination.stat().st_size,
            sha256=_sha256(destination),
            integrity=integrity,
        )


def _read_only_uri(path: Path) -> str:
    return f"file:{path.as_posix()}?mode=ro"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["BackupOperationError", "DatabaseBackupService"]
