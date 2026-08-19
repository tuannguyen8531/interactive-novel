"""Command and runtime contracts for application-level turn use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.domain.state import GameState


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class TurnRunRequest:
    """Provider/graph-neutral request passed to the injected turn runner."""

    turn_run_id: str
    playthrough_id: str
    branch_id: str
    base_revision: int
    raw_input: str
    actor_id: str
    game_state: GameState
    parent_turn_id: str | None = None
    config_snapshot_id: str = "phase-9-default"

    def __post_init__(self) -> None:
        for name in ("turn_run_id", "playthrough_id", "branch_id", "raw_input", "actor_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be blank")
        if self.base_revision < 0:
            raise ValueError("base_revision cannot be negative")
        if self.game_state.playthrough_id != self.playthrough_id or self.game_state.branch_id != self.branch_id:
            raise ValueError("game_state scope does not match the turn request")


@dataclass(frozen=True, slots=True)
class SubmitTurnCommand:
    """Input DTO for submitting one turn through the application boundary."""

    idempotency_key: str
    turn_run_id: str
    playthrough_id: str
    branch_id: str
    base_revision: int
    raw_input: str
    actor_id: str
    game_state: GameState
    parent_turn_id: str | None = None
    config_snapshot_id: str = "phase-9-default"

    def __post_init__(self) -> None:
        for name in ("idempotency_key", "turn_run_id", "playthrough_id", "branch_id", "raw_input", "actor_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be blank")
        if self.base_revision < 0:
            raise ValueError("base_revision cannot be negative")
        if self.game_state.playthrough_id != self.playthrough_id or self.game_state.branch_id != self.branch_id:
            raise ValueError("game_state scope does not match the turn command")

    def run_request(self) -> TurnRunRequest:
        return TurnRunRequest(
            turn_run_id=self.turn_run_id,
            playthrough_id=self.playthrough_id,
            branch_id=self.branch_id,
            base_revision=self.base_revision,
            raw_input=self.raw_input,
            actor_id=self.actor_id,
            game_state=self.game_state,
            parent_turn_id=self.parent_turn_id,
            config_snapshot_id=self.config_snapshot_id,
        )

    def fingerprint(self) -> tuple[Any, ...]:
        """Return the non-secret command fields used for idempotency checks."""
        return (
            self.turn_run_id,
            self.playthrough_id,
            self.branch_id,
            self.base_revision,
            self.raw_input,
            self.actor_id,
            self.parent_turn_id,
            self.config_snapshot_id,
        )


@dataclass(frozen=True, slots=True)
class TurnJobView:
    """Observable state of a submitted turn before or after canonical commit."""

    idempotency_key: str
    turn_run_id: str
    playthrough_id: str
    branch_id: str
    status: str
    result: Any = None
    error: dict[str, Any] | None = None
    cancellation_requested: bool = False
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def as_dict(self) -> dict[str, Any]:
        """Return a safe DTO mapping without exposing a runtime task."""
        return {
            "idempotency_key": self.idempotency_key,
            "turn_run_id": self.turn_run_id,
            "playthrough_id": self.playthrough_id,
            "branch_id": self.branch_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "cancellation_requested": self.cancellation_requested,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


__all__ = ["SubmitTurnCommand", "TurnJobView", "TurnRunRequest"]
