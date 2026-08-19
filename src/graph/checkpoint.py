"""Checkpoint factories for bounded turn runs.

SQLite is the production checkpoint adapter.  Tests should prefer
``InMemorySaver`` so they do not open a database connection merely to exercise
the graph.  The async SQLite context manager is intentionally lazy: importing
this module does not open a connection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver


def build_in_memory_checkpointer() -> InMemorySaver:
    """Return an isolated checkpointer for deterministic graph tests."""

    return InMemorySaver()


@asynccontextmanager
async def sqlite_checkpointer(path: str | Path) -> AsyncIterator[Any]:
    """Open the LangGraph SQLite saver and always close it on exit.

    The connection is not opened until this context is entered.  Callers that
    run in a restricted environment should bound this operation externally.
    """

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        yield saver


def checkpoint_config(turn_run_id: str) -> dict[str, dict[str, str]]:
    """Use the turn run ID as LangGraph's required checkpoint thread ID."""

    if not turn_run_id.strip():
        raise ValueError("turn_run_id is required for checkpoint configuration")
    return {"configurable": {"thread_id": turn_run_id}}


__all__ = ["build_in_memory_checkpointer", "checkpoint_config", "sqlite_checkpointer"]
