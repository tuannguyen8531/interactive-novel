"""Alembic orchestration that works from both CLI and async tests."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def alembic_config() -> Config:
    """Load the repository Alembic configuration."""
    return Config(str(PROJECT_ROOT / "alembic.ini"))


def _upgrade_with_connection(connection: object) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


async def upgrade_database(engine: AsyncEngine) -> None:
    """Upgrade a database to the current migration head."""
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade_with_connection)


__all__ = ["PROJECT_ROOT", "alembic_config", "upgrade_database"]
