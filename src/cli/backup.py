"""Create, restore and inspect canonical SQLite backups."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import get_settings
from src.paths import get_runtime_paths
from src.services.persistence.backup import BackupOperationError, DatabaseBackupService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="interactive-novel backup")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create and verify a SQLite backup.")
    create.add_argument("--database", type=Path, help="Canonical game database path.")
    create.add_argument("--output", type=Path, required=True, help="Backup destination path.")

    restore = subparsers.add_parser("restore", help="Verify and restore a SQLite backup.")
    restore.add_argument("--input", type=Path, required=True, help="Backup source path.")
    restore.add_argument("--database", type=Path, help="Restore destination database path.")

    integrity = subparsers.add_parser("integrity", help="Run SQLite integrity_check.")
    integrity.add_argument("--database", type=Path, help="Canonical game database path.")

    args = parser.parse_args(argv)
    default_database = get_runtime_paths(get_settings().runtime_dir).game_db
    database = args.database or default_database
    service = DatabaseBackupService(database)
    try:
        if args.command == "create":
            result = service.create_backup(args.output)
            print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "restore":
            result = service.restore_backup(args.input, database)
            print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
            return 0
        result = service.integrity_check()
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0 if result.ok else 1
    except BackupOperationError as error:
        print(f"backup error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
