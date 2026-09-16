"""Runtime path management for local-first product data.

The path layout is anchored at the project root by default, while tests and
deployments can provide an explicit runtime directory. This keeps filesystem
policy out of the application and domain layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime"


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Validated locations for canonical and execution runtime artifacts."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.expanduser().resolve())

    @property
    def game_db(self) -> Path:
        """Canonical product database path."""
        return self.db / "game.db"

    @property
    def checkpoints_db(self) -> Path:
        """LangGraph checkpoint database path, separate from game data."""
        return self.db / "checkpoints.db"

    @property
    def db(self) -> Path:
        return self.root / "db"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def settings(self) -> Path:
        return self.root / "settings.json"

    @property
    def presets(self) -> Path:
        return self.root / "presets"

    @property
    def telemetry(self) -> Path:
        return self.logs / "telemetry.jsonl"

    @property
    def feedback(self) -> Path:
        return self.logs / "feedback.jsonl"

    def ensure_directories(self) -> RuntimePaths:
        """Create only the runtime directories owned by this application."""
        for directory in (self.root, self.db, self.logs, self.exports):
            directory.mkdir(parents=True, exist_ok=True)
        for name in ("game.db", "checkpoints.db"):
            self._move_legacy_database(name)
        return self

    def _move_legacy_database(self, name: str) -> None:
        legacy = self.root / name
        destination = self.db / name
        if not legacy.is_file() or destination.exists():
            return
        legacy.replace(destination)
        for suffix in ("-wal", "-shm"):
            sidecar = legacy.with_name(f"{name}{suffix}")
            if sidecar.is_file():
                sidecar.replace(destination.with_name(f"{name}{suffix}"))


def get_runtime_paths(runtime_dir: Path | str | None = None) -> RuntimePaths:
    """Return project-anchored runtime paths unless an explicit root is given."""
    configured_root = Path(runtime_dir) if runtime_dir is not None else DEFAULT_RUNTIME_DIR
    if not configured_root.is_absolute():
        configured_root = PROJECT_ROOT / configured_root
    return RuntimePaths(configured_root)


__all__ = ["DEFAULT_RUNTIME_DIR", "PROJECT_ROOT", "RuntimePaths", "get_runtime_paths"]
