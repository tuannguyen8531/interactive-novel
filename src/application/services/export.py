"""Playthrough export use case built from canonical records and projections."""

from __future__ import annotations

from datetime import UTC, datetime

from src.application.contracts.exports import PlaythroughExport
from src.application.errors import ResourceNotFoundError
from src.application.ports.persistence import UowFactory


class PlaythroughExportApplicationService:
    """Export a complete playthrough without exposing ORM models."""

    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def export_playthrough(self, playthrough_id: str) -> PlaythroughExport:
        async with self._uow_factory() as uow:
            playthrough = await uow.playthroughs.get(playthrough_id)
            if playthrough is None:
                raise ResourceNotFoundError(f"Playthrough {playthrough_id} does not exist.")
            world = await uow.worlds.get(playthrough.world_id)
            if world is None:
                raise ResourceNotFoundError(f"World {playthrough.world_id} does not exist.")
            branches = tuple(await uow.canonical.list_branches(playthrough_id))
            turns = tuple(await uow.canonical.list_turns(playthrough_id))
            characters = tuple(
                await uow.inspection.list_characters(
                    playthrough_id=playthrough_id,
                    world_id=world.id,
                    branch_id=playthrough.active_branch_id,
                )
            )
            events_by_id = {}
            relationships_by_key = {}
            for branch in branches:
                for event in await uow.canonical.list_visible_events(branch.id):
                    events_by_id[event.event_id] = event
                for relationship in await uow.inspection.inspect_relationships(
                    playthrough_id=playthrough_id,
                    branch_id=branch.id,
                ):
                    relationships_by_key[(relationship.branch_id, relationship.source_id, relationship.target_id)] = relationship
            jobs = tuple(job for job in await uow.canonical.list_derived_jobs() if job.playthrough_id == playthrough_id)
        return PlaythroughExport(
            format_version="playthrough-export-1",
            exported_at=datetime.now(UTC),
            world=world,
            playthrough=playthrough,
            branches=branches,
            turns=turns,
            characters=characters,
            events=tuple(sorted(events_by_id.values(), key=lambda item: (item.world_time, item.event_id))),
            relationships=tuple(
                sorted(
                    relationships_by_key.values(),
                    key=lambda item: (item.branch_id, item.source_id, item.target_id),
                )
            ),
            derived_jobs=jobs,
        )


__all__ = ["PlaythroughExportApplicationService"]
