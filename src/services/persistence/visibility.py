"""Resolve the exact canonical turn chain visible from one branch head."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BranchModel, TurnModel


@dataclass(frozen=True, slots=True)
class VisibleBranchScope:
    """Branch ancestry plus the parent-linked turn chain at the selected head."""

    branch_ids: tuple[str, ...]
    turn_ids: tuple[str, ...]

    @property
    def turn_id_set(self) -> frozenset[str]:
        return frozenset(self.turn_ids)


async def resolve_visible_branch_scope(session: AsyncSession, branch_id: str) -> VisibleBranchScope:
    """Return root-to-leaf branches and root-to-head turns without fork leakage."""

    branches: list[BranchModel] = []
    seen_branches: set[str] = set()
    current_branch_id: str | None = branch_id
    while current_branch_id is not None:
        if current_branch_id in seen_branches:
            raise ValueError(f"Branch ancestry cycle detected at {current_branch_id}.")
        seen_branches.add(current_branch_id)
        branch = await session.scalar(select(BranchModel).where(BranchModel.id == current_branch_id))
        if branch is None:
            raise ValueError(f"Branch {current_branch_id} does not exist.")
        branches.append(branch)
        current_branch_id = branch.parent_branch_id
    branches.reverse()

    turns: list[str] = []
    seen_turns: set[str] = set()
    current_turn_id = branches[-1].head_turn_id
    while current_turn_id is not None:
        if current_turn_id in seen_turns:
            raise ValueError(f"Turn ancestry cycle detected at {current_turn_id}.")
        seen_turns.add(current_turn_id)
        turn = await session.scalar(select(TurnModel).where(TurnModel.id == current_turn_id))
        if turn is None:
            raise ValueError(f"Turn {current_turn_id} does not exist.")
        turns.append(turn.id)
        current_turn_id = turn.parent_turn_id
    turns.reverse()
    return VisibleBranchScope(
        branch_ids=tuple(branch.id for branch in branches),
        turn_ids=tuple(turns),
    )


__all__ = ["VisibleBranchScope", "resolve_visible_branch_scope"]
