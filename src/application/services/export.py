"""Playthrough export use case built from canonical records and projections."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

from pydantic import TypeAdapter, ValidationError

from src.application.contracts.ai import WorldSeed
from src.application.contracts.exports import ExportBundle, PlaythroughExport
from src.application.contracts.persistence import BranchRecord, CharacterRole, TurnRecord
from src.application.errors import ApplicationValidationError, ResourceNotFoundError
from src.application.ports.persistence import UowFactory
from src.domain.codec import patch_from_payload
from src.graph.records import build_canonical_bundle
from src.graph.state import TurnGraphState

from .game_states import GameStateApplicationService
from .world_drafts import _build_opening_bundle, _character_record


class PlaythroughExportApplicationService:
    """Export a complete playthrough without exposing ORM models."""

    def __init__(self, uow_factory: UowFactory, *, game_states: GameStateApplicationService | None = None) -> None:
        self._uow_factory = uow_factory
        self._game_states = game_states or GameStateApplicationService(uow_factory)

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
            format_version="playthrough-export",
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

    async def export_bundle(self, playthrough_id: str) -> ExportBundle:
        """Return a checksummed portable envelope for export/import workflows."""
        return ExportBundle.from_export(await self.export_playthrough(playthrough_id))

    @staticmethod
    def validate_import(raw: bytes) -> ExportBundle:
        """Validate a bundle before a future canonical import use case consumes it."""
        try:
            return ExportBundle.from_bytes(raw)
        except ValueError as error:
            raise ApplicationValidationError("Export bundle validation failed.") from error

    async def import_bundle(self, raw: bytes) -> PlaythroughExport:
        """Restore a portable bundle when its canonical identities are unused."""
        envelope = self.validate_import(raw)
        try:
            exported = TypeAdapter(PlaythroughExport).validate_python(envelope.payload)
        except ValidationError as error:
            raise ApplicationValidationError("Export bundle payload does not match the playthrough contract.") from error
        if exported.format_version != "playthrough-export":
            raise ApplicationValidationError("Unsupported playthrough export format.")

        seed_value = exported.world.canon_rules.get("world_seed")
        if not isinstance(seed_value, dict):
            raise ApplicationValidationError("Import requires a confirmed world_seed in canon_rules.")
        try:
            seed = WorldSeed.model_validate(seed_value)
        except ValidationError as error:
            raise ApplicationValidationError("Imported world_seed is invalid.") from error

        async with self._uow_factory() as uow:
            if await uow.worlds.get(exported.world.id) is not None:
                raise ApplicationValidationError(
                    "A world with this ID already exists. Delete it before restoring this exact bundle."
                )
            if await uow.playthroughs.get(exported.playthrough.id) is not None:
                raise ApplicationValidationError("A playthrough with this ID already exists.")

        root = next((item for item in exported.branches if item.id == exported.playthrough.root_branch_id), None)
        if root is None:
            raise ApplicationValidationError("Export bundle is missing its root branch.")
        turns = tuple(exported.turns)
        turns_by_branch = {branch.id: self._ordered_local_turns(branch, turns) for branch in exported.branches}
        root_turns = turns_by_branch[root.id]
        if not root_turns or root_turns[0].approved_patch is None:
            raise ApplicationValidationError("Export bundle is missing its opening turn.")
        opening = root_turns[0]
        opening_event = next((item for item in exported.events if item.turn_id == opening.id), None)
        if opening_event is None:
            raise ApplicationValidationError("Export bundle is missing its opening event.")

        initial_playthrough = replace(
            exported.playthrough,
            root_branch_id=None,
            active_branch_id=None,
            world_clock_minutes=opening.world_time_start,
        )
        initial_root = replace(root, head_turn_id=None, head_revision=0)
        try:
            characters = (_character_record(exported.world.id, seed.player_character, role=CharacterRole.PLAYER),) + tuple(
                _character_record(exported.world.id, item, role=CharacterRole.NPC) for item in seed.npc_profiles
            )
        except ValueError as error:
            raise ApplicationValidationError("Imported world_seed must use UUID character IDs.") from error
        opening_bundle = _build_opening_bundle(
            seed,
            playthrough=initial_playthrough,
            branch=initial_root,
            turn_id=opening.id,
            event_id=opening_event.event_id,
            turn_run_id=opening.turn_run_id,
        )
        opening_bundle = replace(
            opening_bundle,
            raw_input=opening.raw_input,
            normalized_input=opening.normalized_input,
            final_narrative=opening.final_narrative or opening_bundle.final_narrative,
            approved_patch=dict(cast(dict[str, object], opening.approved_patch)),
            suggested_actions=opening.suggested_actions,
        )

        try:
            async with self._uow_factory() as uow:
                await uow.worlds.add(exported.world)
                for character in characters:
                    await uow.characters.add(character)
                await uow.playthroughs.add(initial_playthrough)
                await uow.canonical.add_branch(initial_root)
                await uow.playthroughs.set_root_branch(initial_playthrough.id, initial_root.id)
                await uow.canonical.commit_turn(opening_bundle)
                await uow.commit()

            for turn in root_turns[1:]:
                await self._import_turn(turn)

            descendants = sorted((item for item in exported.branches if item.id != root.id), key=lambda item: item.depth)
            for branch in descendants:
                imported_branch = replace(branch, head_turn_id=branch.fork_turn_id, head_revision=0)
                async with self._uow_factory() as uow:
                    await uow.canonical.add_branch(imported_branch)
                    await uow.commit()
                for turn in turns_by_branch[branch.id]:
                    await self._import_turn(turn)

            active_branch_id = exported.playthrough.active_branch_id or root.id
            async with self._uow_factory() as uow:
                await uow.playthroughs.set_active_branch(exported.playthrough.id, active_branch_id)
                active_branch = await uow.canonical.get_branch(active_branch_id)
                head = (
                    None
                    if active_branch is None or active_branch.head_turn_id is None
                    else await uow.canonical.get_turn(active_branch.head_turn_id)
                )
                await uow.playthroughs.set_world_clock(
                    exported.playthrough.id,
                    opening.world_time_start if head is None else head.world_time_end,
                )
                await uow.commit()
        except Exception:
            async with self._uow_factory() as uow:
                await uow.worlds.delete(exported.world.id)
                await uow.commit()
            raise

        return await self.export_playthrough(exported.playthrough.id)

    async def _import_turn(self, turn: TurnRecord) -> None:
        if turn.approved_patch is None or turn.final_narrative is None:
            raise ApplicationValidationError(f"Turn {turn.id} is missing canonical output.")
        try:
            patch_from_payload(turn.approved_patch)
        except (TypeError, ValueError) as error:
            raise ApplicationValidationError(f"Turn {turn.id} has an unsupported approved patch.") from error
        state = await self._game_states.load(playthrough_id=turn.playthrough_id, branch_id=turn.branch_id)
        graph_state = cast(
            TurnGraphState,
            {
                "playthrough_id": turn.playthrough_id,
                "branch_id": turn.branch_id,
                "raw_input": turn.raw_input,
                "normalized_input": turn.normalized_input,
                "base_revision": turn.base_revision,
                "parent_turn_id": turn.parent_turn_id,
                "turn_run_id": turn.turn_run_id,
                "approved_patch": turn.approved_patch,
                "final_narrative": turn.final_narrative,
            },
        )
        rebuilt = build_canonical_bundle(graph_state, state)
        if rebuilt.turn_id != turn.id:
            raise ApplicationValidationError(f"Turn {turn.id} uses an incompatible turn identity.")
        rebuilt = replace(rebuilt, suggested_actions=turn.suggested_actions)
        async with self._uow_factory() as uow:
            await uow.canonical.commit_turn(rebuilt)
            await uow.commit()

    @staticmethod
    def _ordered_local_turns(branch: BranchRecord, turns: tuple[TurnRecord, ...]) -> tuple[TurnRecord, ...]:
        local = {item.id: item for item in turns if item.branch_id == branch.id}
        ordered: list[TurnRecord] = []
        parent_id = branch.fork_turn_id
        while local:
            candidates = [item for item in local.values() if item.parent_turn_id == parent_id]
            if len(candidates) != 1:
                raise ApplicationValidationError(f"Branch {branch.id} does not contain one linear local turn chain.")
            current = candidates[0]
            ordered.append(current)
            parent_id = current.id
            del local[current.id]
        return tuple(ordered)


__all__ = ["PlaythroughExportApplicationService"]
