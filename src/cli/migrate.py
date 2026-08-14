"""Run the canonical game database migrations."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.config import get_settings
from src.paths import get_runtime_paths
from src.services.persistence.database import create_database
from src.services.persistence.migrations import upgrade_database


async def _migrate(database_path: Path) -> None:
    database = create_database(database_path=database_path, busy_timeout_ms=get_settings().database_busy_timeout_ms)
    try:
        await upgrade_database(database.engine)
    finally:
        await database.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upgrade the canonical game database to the latest revision.")
    parser.add_argument("--database", type=Path, help="Override the runtime game.db path.")
    args = parser.parse_args(argv)
    database_path = args.database or get_runtime_paths(get_settings().runtime_dir).game_db
    asyncio.run(_migrate(database_path))
    print(f"Database migrated: {database_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
