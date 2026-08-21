"""Ports for scheduling turn execution without coupling application to LangGraph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from src.application.contracts.turns import TurnRunRequest


class TurnRunner(Protocol):
    """Injected turn executor; the graph is one implementation."""

    async def run(self, request: TurnRunRequest) -> Mapping[str, Any] | Any: ...

    def cancel(self, turn_run_id: str) -> None: ...


__all__ = ["TurnRunner"]
