"""Contracts returned by database backup and integrity operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    path: str
    ok: bool
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "ok": self.ok, "message": self.message}


@dataclass(frozen=True, slots=True)
class DatabaseBackupReport:
    source_path: str
    destination_path: str
    size_bytes: int
    sha256: str
    integrity: IntegrityReport

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "destination_path": self.destination_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "integrity": self.integrity.as_dict(),
        }


__all__ = ["DatabaseBackupReport", "IntegrityReport"]
