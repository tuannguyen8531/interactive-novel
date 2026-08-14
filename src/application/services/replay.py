"""Replay application service using snapshot fallback plus approved patches."""

from __future__ import annotations

from src.application.ports.persistence import UowFactory
from src.domain.codec import patch_from_payload, state_from_payload
from src.domain.engine import DomainEngine
from src.domain.state import GameState


class ReplayApplicationService:
    """Rebuild a branch without treating a snapshot as canonical authority."""

    def __init__(self, uow_factory: UowFactory, *, engine: DomainEngine | None = None) -> None:
        self._uow_factory = uow_factory
        self._engine = engine or DomainEngine()

    async def replay_branch(self, *, branch_id: str, initial_state: GameState) -> GameState:
        async with self._uow_factory() as uow:
            snapshot = await uow.canonical.load_latest_snapshot(branch_id)
            after_revision = 0
            state = initial_state.copy()
            if snapshot is not None:
                state = state_from_payload(snapshot.state_payload)
                after_revision = snapshot.source_revision
            payloads = await uow.canonical.list_approved_patches(branch_id, after_revision=after_revision)
        for _, payload in payloads:
            state = self._engine.apply(state, patch_from_payload(payload)).after
        return state


__all__ = ["ReplayApplicationService"]
