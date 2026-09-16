"""Secret-free JSON persistence for local provider routing settings."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from uuid import uuid4


class JsonProviderSettingsStore:
    """Persist one small settings document using an atomic replacement."""

    def __init__(self, path: Path) -> None:
        self._path = path

    async def get(self) -> dict[str, object] | None:
        if not self._path.is_file():
            return None
        value = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Provider settings must contain a JSON object.")
        return dict(value)

    async def put(self, snapshot: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self._path)
        finally:
            temporary.unlink(missing_ok=True)


class JsonProviderPresetStore:
    """Persist each named preset as one JSON file."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    async def list_names(self) -> list[str]:
        if not self._directory.is_dir():
            return []
        return sorted(self._read(path)[0] for path in self._directory.glob("*.json"))

    async def get(self, name: str) -> dict[str, object] | None:
        path = self._path(name)
        if not path.is_file():
            return None
        stored_name, snapshot = self._read(path)
        if stored_name != name:
            return None
        return snapshot

    async def put(self, name: str, snapshot: dict[str, object]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._path(name)
        if path.exists():
            stored_name, _ = self._read(path)
            if stored_name != name:
                raise FileExistsError(path)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps({"name": name, "settings": snapshot}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    async def delete(self, name: str) -> bool:
        path = self._path(name)
        if not path.is_file():
            return False
        stored_name, _ = self._read(path)
        if stored_name != name:
            return False
        path.unlink()
        return True

    def _path(self, name: str) -> Path:
        normalized = unicodedata.normalize("NFKD", name)
        ascii_name = normalized.encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
        if not slug:
            raise ValueError("Preset name must contain at least one letter or number.")
        return self._directory / f"{slug}.json"

    @staticmethod
    def _read(path: Path) -> tuple[str, dict[str, object]]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Preset file {path.name} is malformed.")
        name = value.get("name")
        settings = value.get("settings")
        if not isinstance(name, str) or not isinstance(settings, dict):
            raise ValueError(f"Preset file {path.name} is malformed.")
        return name, settings


__all__ = ["JsonProviderPresetStore", "JsonProviderSettingsStore"]
