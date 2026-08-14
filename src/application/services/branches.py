"""Branch creation, fork/regenerate and ancestry use cases."""

from __future__ import annotations

from src.application.contracts.persistence import BranchRecord
from src.application.errors import ResourceConflictError, ResourceNotFoundError
from src.application.ports.persistence import UowFactory


class BranchApplicationService:
    """Keep branch lifecycle and fork semantics inside application transactions."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def create_root_branch(self, *, playthrough_id: str, branch_id: str | None = None) -> BranchRecord:
        branch = BranchRecord.root(playthrough_id=playthrough_id, branch_id=branch_id)
        async with self._uow_factory() as uow:
            if await uow.playthroughs.get(playthrough_id) is None:
                raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
            await uow.canonical.add_branch(branch)
            await uow.playthroughs.set_root_branch(playthrough_id, branch.id)
            await uow.commit()
        return branch

    async def fork_branch(
        self,
        *,
        parent_branch_id: str,
        fork_turn_id: str,
        branch_id: str | None = None,
    ) -> BranchRecord:
        async with self._uow_factory() as uow:
            parent = await uow.canonical.get_branch(parent_branch_id)
            if parent is None:
                raise ResourceNotFoundError(f"Branch {parent_branch_id} does not exist.")
            if parent.lifecycle != "active":
                raise ResourceConflictError("Cannot fork an abandoned branch.")
            turn = await uow.canonical.get_turn(fork_turn_id)
            if turn is None or turn.branch_id != parent_branch_id:
                raise ResourceNotFoundError(f"Fork turn {fork_turn_id} is not on branch {parent_branch_id}.")
            child = BranchRecord(
                id=branch_id or BranchRecord.root(playthrough_id=parent.playthrough_id).id,
                playthrough_id=parent.playthrough_id,
                parent_branch_id=parent.id,
                fork_turn_id=fork_turn_id,
                head_turn_id=fork_turn_id,
                depth=parent.depth + 1,
                head_revision=0,
            )
            await uow.canonical.add_branch(child)
            await uow.commit()
            return child

    async def regenerate_branch(
        self,
        *,
        parent_branch_id: str,
        fork_turn_id: str,
        branch_id: str | None = None,
    ) -> BranchRecord:
        """Regeneration is a new branch, never an overwrite of published history."""
        return await self.fork_branch(
            parent_branch_id=parent_branch_id,
            fork_turn_id=fork_turn_id,
            branch_id=branch_id,
        )

    async def list_ancestry(self, branch_id: str) -> list[BranchRecord]:
        async with self._uow_factory() as uow:
            try:
                return await uow.canonical.get_branch_ancestry(branch_id)
            except RuntimeError as error:
                raise ResourceNotFoundError(str(error)) from error


__all__ = ["BranchApplicationService"]
