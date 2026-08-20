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
        branch_id: str | None = None,
        turn_id: str | None = None,
        new_branch_id: str | None = None,
        parent_branch_id: str | None = None,
        fork_turn_id: str | None = None,
    ) -> BranchRecord:
        """Create a history-preserving branch immediately before one turn."""
        if parent_branch_id is not None and fork_turn_id is not None:
            return await self.fork_branch(
                parent_branch_id=parent_branch_id,
                fork_turn_id=fork_turn_id,
                branch_id=new_branch_id or branch_id,
            )
        if branch_id is not None and turn_id is not None:
            return await self._branch_before_turn(branch_id=branch_id, turn_id=turn_id, new_branch_id=new_branch_id)
        raise ValueError("Regenerate requires branch_id/turn_id or parent_branch_id/fork_turn_id.")

    async def undo_branch(
        self,
        *,
        branch_id: str,
        head_turn_id: str,
        new_branch_id: str | None = None,
    ) -> BranchRecord:
        """Undo the current head by activating a new branch at its parent."""
        async with self._uow_factory() as uow:
            branch = await uow.canonical.get_branch(branch_id)
            if branch is None:
                raise ResourceNotFoundError(f"Branch {branch_id} does not exist.")
            if branch.head_turn_id != head_turn_id:
                raise ResourceConflictError("Undo target is no longer the branch head.")
        child = await self._branch_before_turn(
            branch_id=branch_id,
            turn_id=head_turn_id,
            new_branch_id=new_branch_id,
        )
        await self.switch_branch(playthrough_id=child.playthrough_id, branch_id=child.id)
        return child

    async def switch_branch(self, *, playthrough_id: str, branch_id: str) -> BranchRecord:
        """Make an existing active branch the playthrough's selected branch."""
        async with self._uow_factory() as uow:
            playthrough = await uow.playthroughs.get(playthrough_id)
            if playthrough is None:
                raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
            branch = await uow.canonical.get_branch(branch_id)
            if branch is None or branch.playthrough_id != playthrough_id:
                raise ResourceNotFoundError(f"Branch {branch_id} does not belong to playthrough {playthrough_id}.")
            if branch.lifecycle != "active":
                raise ResourceConflictError("Cannot switch to an abandoned branch.")
            await uow.playthroughs.set_active_branch(playthrough_id, branch_id)
            head = None if branch.head_turn_id is None else await uow.canonical.get_turn(branch.head_turn_id)
            await uow.playthroughs.set_world_clock(playthrough_id, 0 if head is None else head.world_time_end)
            await uow.commit()
            return branch

    async def _branch_before_turn(
        self,
        *,
        branch_id: str,
        turn_id: str,
        new_branch_id: str | None,
    ) -> BranchRecord:
        async with self._uow_factory() as uow:
            branch = await uow.canonical.get_branch(branch_id)
            turn = await uow.canonical.get_turn(turn_id)
            if branch is None:
                raise ResourceNotFoundError(f"Branch {branch_id} does not exist.")
            if turn is None or turn.playthrough_id != branch.playthrough_id:
                raise ResourceNotFoundError(f"Turn {turn_id} does not belong to this playthrough.")
            visible = await uow.canonical.list_visible_turns(branch_id)
            if turn.id not in {item.id for item in visible}:
                raise ResourceNotFoundError(f"Turn {turn_id} is not visible on branch {branch_id}.")
            if turn.parent_turn_id is None:
                raise ResourceConflictError("The opening scene cannot be regenerated or undone.")
            parent_turn = await uow.canonical.get_turn(turn.parent_turn_id)
            if parent_turn is None:
                raise ResourceNotFoundError(f"Parent turn {turn.parent_turn_id} does not exist.")

            if parent_turn.branch_id == branch.id:
                parent_branch = branch
            elif branch.parent_branch_id is not None and branch.fork_turn_id == parent_turn.id:
                parent_branch = await uow.canonical.get_branch(branch.parent_branch_id)
                if parent_branch is None:
                    raise ResourceNotFoundError(f"Parent branch {branch.parent_branch_id} does not exist.")
            else:
                raise ResourceConflictError("Turn ancestry cannot be branched safely.")

            child = BranchRecord(
                id=new_branch_id or BranchRecord.root(playthrough_id=branch.playthrough_id).id,
                playthrough_id=branch.playthrough_id,
                parent_branch_id=parent_branch.id,
                fork_turn_id=parent_turn.id,
                head_turn_id=parent_turn.id,
                depth=parent_branch.depth + 1,
                head_revision=0,
            )
            await uow.canonical.add_branch(child)
            await uow.commit()
            return child

    async def list_ancestry(self, branch_id: str) -> list[BranchRecord]:
        async with self._uow_factory() as uow:
            try:
                return await uow.canonical.get_branch_ancestry(branch_id)
            except RuntimeError as error:
                raise ResourceNotFoundError(str(error)) from error


__all__ = ["BranchApplicationService"]
