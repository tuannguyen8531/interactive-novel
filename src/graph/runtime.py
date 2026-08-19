"""Runtime-only dependencies for one turn graph invocation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from src.application.contracts.persistence import CanonicalTurnBundle
from src.application.contracts.providers import CancellationToken, ExecutionMode
from src.application.ports.providers import ProviderPort
from src.application.ports.retrieval import MemoryCandidateSource
from src.domain.guard import DomainGuard
from src.domain.state import GameState

from .events import AsyncEventCallback, EventSink


class TurnCommitter(Protocol):
    """Application boundary used by the graph's canonical commit node."""

    async def commit_turn(self, bundle: CanonicalTurnBundle) -> Any: ...


DerivedJobHandler = Callable[[tuple[dict[str, Any], ...], CanonicalTurnBundle], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class TurnPipelineRequest:
    """Immutable request metadata; the domain state remains a runtime input."""

    turn_run_id: str
    playthrough_id: str
    branch_id: str
    base_revision: int
    raw_input: str
    actor_id: str
    game_state: GameState
    parent_turn_id: str | None = None
    config_snapshot_id: str = "phase-8-default"

    def __post_init__(self) -> None:
        for name in ("turn_run_id", "playthrough_id", "branch_id", "raw_input", "actor_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be blank")
        if self.base_revision < 0:
            raise ValueError("base_revision cannot be negative")
        if self.game_state.playthrough_id != self.playthrough_id or self.game_state.branch_id != self.branch_id:
            raise ValueError("game_state scope does not match the turn request")


@dataclass(slots=True)
class TurnGraphRuntime:
    """Non-checkpointed services captured by graph node closures."""

    request: TurnPipelineRequest
    provider: ProviderPort
    candidate_source: MemoryCandidateSource | None
    committer: TurnCommitter
    guard: DomainGuard
    cancellation: CancellationToken | None = None
    execution_mode: ExecutionMode = ExecutionMode.QUALITY
    event_sink: EventSink | AsyncEventCallback | None = None
    derived_job_handler: DerivedJobHandler | None = None
    max_repair_attempts: int = 1
    max_revision_attempts: int = 1
    max_contract_retries: int = 1
    failure_hook: Callable[[str], None] | None = None


__all__ = [
    "DerivedJobHandler",
    "TurnCommitter",
    "TurnGraphRuntime",
    "TurnPipelineRequest",
]
