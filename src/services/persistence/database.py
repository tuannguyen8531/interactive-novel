"""Async SQLAlchemy engine and SQLite connection policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import URL, event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.paths import RuntimePaths, get_runtime_paths


async def _configure_async_sqlite_connection(raw_connection: Any, busy_timeout_ms: int) -> None:
    for statement in (
        "PRAGMA foreign_keys = ON",
        "PRAGMA journal_mode = WAL",
        f"PRAGMA busy_timeout = {busy_timeout_ms}",
    ):
        cursor = await raw_connection.execute(statement)
        await cursor.close()


def _configure_sqlite_connection(dbapi_connection: Any, _connection_record: Any, busy_timeout_ms: int) -> None:
    """Configure aiosqlite through its async bridge inside SQLAlchemy's event."""
    run_async = getattr(dbapi_connection, "run_async", None)
    if run_async is not None:
        run_async(lambda raw_connection: _configure_async_sqlite_connection(raw_connection, busy_timeout_ms))
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
    finally:
        cursor.close()


@dataclass(slots=True)
class Database:
    """An async engine plus session factory for one canonical game database."""

    path: Path
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    async def dispose(self) -> None:
        await self.engine.dispose()


def create_database(
    runtime: RuntimePaths | None = None,
    *,
    database_path: Path | None = None,
    busy_timeout_ms: int = 5_000,
    echo: bool = False,
) -> Database:
    """Create an async SQLite database handle with the locked PRAGMAs."""
    if busy_timeout_ms < 0:
        raise ValueError("busy_timeout_ms cannot be negative.")
    paths = runtime or get_runtime_paths()
    path = (database_path or paths.game_db).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    database_url = URL.create("sqlite+aiosqlite", database=str(path))
    engine = create_async_engine(
        database_url,
        echo=echo,
        connect_args={"timeout": busy_timeout_ms / 1_000},
    )

    def configure_connection(dbapi_connection: Any, connection_record: Any) -> None:
        _configure_sqlite_connection(dbapi_connection, connection_record, busy_timeout_ms)

    event.listen(engine.sync_engine, "connect", configure_connection)
    return Database(
        path=path,
        engine=engine,
        session_factory=async_sessionmaker(engine, expire_on_commit=False, autoflush=False),
    )


__all__ = ["Database", "create_database"]
