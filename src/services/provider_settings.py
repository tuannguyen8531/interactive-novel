"""Secret-free JSON persistence for local provider routing settings."""

from __future__ import annotations

import json
import os
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


__all__ = ["JsonProviderSettingsStore"]
