"""Safe first-run readiness checks with no provider network calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import get_settings
from src.paths import get_runtime_paths
from src.services.persistence.backup import DatabaseBackupService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="interactive-novel doctor")
    parser.add_argument("--runtime", type=Path, help="Override the runtime directory.")
    parser.add_argument("--strict", action="store_true", help="Fail when the database has not been initialized.")
    args = parser.parse_args(argv)

    settings = get_settings()
    runtime = get_runtime_paths(args.runtime or settings.runtime_dir).ensure_directories()
    integrity = DatabaseBackupService(runtime.game_db).integrity_check()
    payload = {
        "runtime": str(runtime.root),
        "game_db": str(runtime.game_db),
        "checkpoints_db": str(runtime.checkpoints_db),
        "logs": str(runtime.logs),
        "exports": str(runtime.exports),
        "telemetry_enabled": settings.telemetry_enabled,
        "database": integrity.as_dict(),
        "first_run": not runtime.game_db.exists(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.strict and not integrity.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
