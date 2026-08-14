from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio

from src.paths import RuntimePaths
from src.services.persistence.database import Database, create_database
from src.services.persistence.migrations import upgrade_database


@pytest_asyncio.fixture
async def empty_database(tmp_path) -> AsyncIterator[Database]:
    database = create_database(RuntimePaths(tmp_path / "runtime"))
    try:
        yield database
    finally:
        await database.dispose()


@pytest_asyncio.fixture
async def database(tmp_path) -> AsyncIterator[Database]:
    database = create_database(RuntimePaths(tmp_path / "runtime"))
    await upgrade_database(database.engine)
    try:
        yield database
    finally:
        await database.dispose()
