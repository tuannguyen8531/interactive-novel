"""Serializable export contract for one complete playthrough."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from src.application.contracts.persistence import (
    BranchRecord,
    DerivedJobRecord,
    EventRecord,
    PlaythroughRecord,
    RelationshipRecord,
    TurnRecord,
    WorldRecord,
)
from src.application.contracts.queries import CharacterView


@dataclass(frozen=True, slots=True)
class PlaythroughExport:
    """Canonical and inspectable data needed to restore or review a run."""

    format_version: str
    exported_at: datetime
    world: WorldRecord
    playthrough: PlaythroughRecord
    branches: tuple[BranchRecord, ...] = ()
    turns: tuple[TurnRecord, ...] = ()
    characters: tuple[CharacterView, ...] = ()
    events: tuple[EventRecord, ...] = ()
    relationships: tuple[RelationshipRecord, ...] = ()
    derived_jobs: tuple[DerivedJobRecord, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Convert records to JSON-compatible primitive values."""
        return _json_safe(asdict(self))


@dataclass(frozen=True, slots=True)
class ExportBundle:
    """Checksummed JSON envelope used for portable export/import validation."""

    format_version: str
    exported_at: str
    payload: dict[str, Any]
    sha256: str

    @classmethod
    def from_export(cls, exported: PlaythroughExport) -> ExportBundle:
        payload = exported.as_dict()
        return cls(
            format_version="playthrough-export-bundle-1",
            exported_at=exported.exported_at.isoformat(),
            payload=payload,
            sha256=_payload_hash(payload),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> ExportBundle:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("export bundle is not valid UTF-8 JSON") from error
        if not isinstance(value, dict):
            raise ValueError("export bundle must be a JSON object")
        format_version = value.get("format_version")
        exported_at = value.get("exported_at")
        payload = value.get("payload")
        sha256 = value.get("sha256")
        if not isinstance(format_version, str) or not isinstance(exported_at, str) or not isinstance(sha256, str):
            raise ValueError("export bundle metadata is invalid")
        if format_version != "playthrough-export-bundle-1" or not isinstance(payload, dict):
            raise ValueError("unsupported export bundle format")
        playthrough = payload.get("playthrough")
        if not isinstance(playthrough, dict) or not isinstance(playthrough.get("id"), str):
            raise ValueError("export bundle is missing a playthrough identity")
        bundle = cls(format_version, exported_at, payload, sha256)
        bundle.verify()
        return bundle

    def as_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "exported_at": self.exported_at,
            "payload": self.payload,
            "sha256": self.sha256,
        }

    def as_bytes(self) -> bytes:
        self.verify()
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def verify(self) -> None:
        """Reject tampering before an import/restore workflow consumes payload."""
        if self.sha256 != _payload_hash(self.payload):
            raise ValueError("export bundle checksum does not match payload")


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


__all__ = ["ExportBundle", "PlaythroughExport"]
