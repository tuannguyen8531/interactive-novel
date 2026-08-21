"""SQLAlchemy adapter for canonical commits and derived artifacts."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.contracts.persistence import (
    BranchRecord,
    CanonicalTurnBundle,
    DerivedJobRecord,
    EventRecord,
    InvariantReport,
    PersistenceIdempotencyConflictError,
    PersistenceNotFoundError,
    PersistenceSnapshotError,
    PersistenceStaleHeadError,
    SnapshotRecord,
    TurnRecord,
    utc_now,
)

from .models import (
    BeliefEvidenceModel,
    BeliefModel,
    BranchModel,
    CanonFactModel,
    CharacterStateModel,
    ClaimLinkModel,
    DerivedJobModel,
    EmotionalTensionModel,
    EventModel,
    EventParticipantModel,
    KnowledgeClaimModel,
    NarrativeHookModel,
    NarrativeThreadModel,
    ObservationModel,
    OutboxEventModel,
    PlaythroughModel,
    RelationshipChangeModel,
    RelationshipModel,
    SnapshotModel,
    TurnModel,
)


class InjectedCommitFailure(RuntimeError):
    """Test-only failure used to verify atomic rollback at a named commit step."""


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _branch_record(model: BranchModel) -> BranchRecord:
    return BranchRecord(
        id=model.id,
        playthrough_id=model.playthrough_id,
        parent_branch_id=model.parent_branch_id,
        fork_turn_id=model.fork_turn_id,
        head_turn_id=model.head_turn_id,
        depth=model.depth,
        head_revision=model.head_revision,
        lifecycle=model.lifecycle,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _turn_record(model: TurnModel) -> TurnRecord:
    return TurnRecord(
        id=model.id,
        playthrough_id=model.playthrough_id,
        branch_id=model.branch_id,
        parent_turn_id=model.parent_turn_id,
        raw_input=model.raw_input,
        normalized_input=model.normalized_input,
        base_revision=model.base_revision,
        status=model.status,
        final_narrative=model.final_narrative,
        approved_patch=None if model.approved_patch is None else dict(model.approved_patch),
        world_time_start=model.world_time_start,
        duration_minutes=model.duration_minutes,
        world_time_end=model.world_time_end,
        turn_run_id=model.turn_run_id,
        schema_version=model.schema_version,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
        suggested_actions=tuple(dict(item) for item in model.suggested_actions),
    )


def _event_record(model: EventModel, participants: Iterable[EventParticipantModel]) -> EventRecord:
    participant_list = list(participants)
    return EventRecord(
        event_id=model.id,
        playthrough_id=model.playthrough_id,
        branch_id=model.branch_id,
        turn_id=model.turn_id,
        event_type=model.event_type,
        world_time=model.world_time,
        location_id=model.location_id,
        actor_ids=tuple(item.participant_id for item in participant_list if item.role == "actor"),
        target_ids=tuple(item.participant_id for item in participant_list if item.role == "target"),
        witness_ids=tuple(item.participant_id for item in participant_list if item.role == "witness"),
        payload=dict(model.payload),
        salience=model.salience,
        emotional_intensity=model.emotional_intensity,
        cause_event_ids=tuple(model.cause_event_ids),
        provenance=dict(model.provenance),
        schema_version=model.schema_version,
    )


def _snapshot_record(model: SnapshotModel) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id=model.id,
        playthrough_id=model.playthrough_id,
        branch_id=model.branch_id,
        source_turn_id=model.source_turn_id,
        source_revision=model.source_revision,
        world_clock_minutes=model.world_clock_minutes,
        rng_state=deepcopy(model.rng_state),
        state_payload=dict(model.state_payload),
        checksum=model.checksum,
        builder_version=model.builder_version,
        schema_version=model.schema_version,
        created_at=_as_utc(model.created_at),
    )


def _derived_job_record(model: DerivedJobModel) -> DerivedJobRecord:
    return DerivedJobRecord(
        id=model.id,
        idempotency_key=model.idempotency_key,
        job_type=model.job_type,
        playthrough_id=model.playthrough_id,
        branch_id=model.branch_id,
        source_turn_id=model.source_turn_id,
        source_revision=model.source_revision,
        payload=dict(model.payload),
        status=model.status,
        attempts=model.attempts,
        last_error=model.last_error,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


class SqlAlchemyCanonicalRepository:
    """Canonical persistence adapter; callers own the surrounding transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_branch(self, branch: BranchRecord) -> None:
        self._session.add(
            BranchModel(
                id=branch.id,
                playthrough_id=branch.playthrough_id,
                parent_branch_id=branch.parent_branch_id,
                fork_turn_id=branch.fork_turn_id,
                head_turn_id=branch.head_turn_id,
                depth=branch.depth,
                head_revision=branch.head_revision,
                lifecycle=branch.lifecycle,
                created_at=branch.created_at,
                updated_at=branch.updated_at,
            )
        )
        await self._session.flush()

    async def get_branch(self, branch_id: str) -> BranchRecord | None:
        model = await self._session.scalar(select(BranchModel).where(BranchModel.id == branch_id))
        return None if model is None else _branch_record(model)

    async def get_turn(self, turn_id: str) -> TurnRecord | None:
        model = await self._session.scalar(select(TurnModel).where(TurnModel.id == turn_id))
        return None if model is None else _turn_record(model)

    async def get_turn_by_run_id(self, turn_run_id: str) -> TurnRecord | None:
        model = await self._session.scalar(select(TurnModel).where(TurnModel.turn_run_id == turn_run_id))
        return None if model is None else _turn_record(model)

    async def list_branches(self, playthrough_id: str) -> list[BranchRecord]:
        models = list(
            (
                await self._session.scalars(
                    select(BranchModel)
                    .where(BranchModel.playthrough_id == playthrough_id)
                    .order_by(BranchModel.depth, BranchModel.created_at, BranchModel.id)
                )
            ).all()
        )
        return [_branch_record(model) for model in models]

    async def list_turns(self, playthrough_id: str, *, branch_id: str | None = None) -> list[TurnRecord]:
        statement = select(TurnModel).where(TurnModel.playthrough_id == playthrough_id)
        if branch_id is not None:
            statement = statement.where(TurnModel.branch_id == branch_id)
        statement = statement.order_by(TurnModel.created_at, TurnModel.id)
        return [_turn_record(model) for model in (await self._session.scalars(statement)).all()]

    async def list_visible_turns(self, branch_id: str) -> list[TurnRecord]:
        _, turn_ids = await self._visible_turn_ids(branch_id)
        if not turn_ids:
            return []
        models = list(
            (
                await self._session.scalars(select(TurnModel).where(TurnModel.id.in_(turn_ids), TurnModel.status == "completed"))
            ).all()
        )
        by_id = {model.id: model for model in models}
        return [_turn_record(by_id[turn_id]) for turn_id in reversed(turn_ids) if turn_id in by_id]

    async def get_branch_ancestry(self, branch_id: str) -> list[BranchRecord]:
        records: list[BranchRecord] = []
        seen: set[str] = set()
        current_id: str | None = branch_id
        while current_id is not None:
            if current_id in seen:
                raise PersistenceNotFoundError(f"Branch ancestry cycle detected at {current_id}.")
            seen.add(current_id)
            model = await self._session.scalar(select(BranchModel).where(BranchModel.id == current_id))
            if model is None:
                raise PersistenceNotFoundError(f"Branch {current_id} does not exist.")
            records.append(_branch_record(model))
            current_id = model.parent_branch_id
        records.reverse()
        return records

    async def verify_invariants(self, branch_id: str) -> InvariantReport:
        branch = await self._session.scalar(select(BranchModel).where(BranchModel.id == branch_id))
        if branch is None:
            raise PersistenceNotFoundError(f"Branch {branch_id} does not exist.")

        violations: list[str] = []
        ancestry = await self.get_branch_ancestry(branch_id)
        ancestry_ids = {item.id for item in ancestry}
        local_turns = list(
            (
                await self._session.scalars(
                    select(TurnModel)
                    .where(TurnModel.branch_id == branch_id)
                    .order_by(TurnModel.base_revision, TurnModel.created_at, TurnModel.id)
                )
            ).all()
        )
        if len(local_turns) != branch.head_revision:
            violations.append("branch_head_revision_does_not_match_local_turn_count")

        expected_parent_id = branch.fork_turn_id
        for expected_revision, turn in enumerate(local_turns):
            if turn.base_revision != expected_revision:
                violations.append(f"turn_revision_gap:{turn.id}")
            if turn.parent_turn_id != expected_parent_id:
                violations.append(f"turn_parent_mismatch:{turn.id}")
            if turn.playthrough_id != branch.playthrough_id:
                violations.append(f"turn_playthrough_mismatch:{turn.id}")
            if turn.world_time_end != turn.world_time_start + turn.duration_minutes:
                violations.append(f"turn_clock_mismatch:{turn.id}")
            expected_parent_id = turn.id

        expected_head_id = expected_parent_id
        if branch.head_turn_id != expected_head_id:
            violations.append("branch_head_turn_does_not_match_local_turn_chain")

        if branch.fork_turn_id is not None:
            fork_turn = await self._session.scalar(select(TurnModel).where(TurnModel.id == branch.fork_turn_id))
            if fork_turn is None:
                violations.append("fork_turn_missing")
            elif fork_turn.branch_id not in ancestry_ids or fork_turn.branch_id == branch_id:
                violations.append("fork_turn_outside_parent_ancestry")

        snapshots = list((await self._session.scalars(select(SnapshotModel).where(SnapshotModel.branch_id == branch_id))).all())
        for snapshot in snapshots:
            if not _snapshot_record(snapshot).is_valid():
                violations.append(f"snapshot_checksum_mismatch:{snapshot.id}")
            if snapshot.source_revision > branch.head_revision:
                violations.append(f"snapshot_revision_ahead_of_head:{snapshot.id}")

        return InvariantReport(branch_id=branch_id, valid=not violations, violations=tuple(violations))

    async def commit_turn(
        self,
        bundle: CanonicalTurnBundle,
        *,
        fail_after_step: str | None = None,
    ) -> TurnRecord:
        """Atomically append a turn and every canonical artifact it owns."""
        existing = await self._session.scalar(select(TurnModel).where(TurnModel.turn_run_id == bundle.turn_run_id))
        if existing is not None:
            if existing.branch_id != bundle.branch_id or existing.raw_input != bundle.raw_input:
                raise PersistenceIdempotencyConflictError("turn_run_id was reused for a different turn.")
            return _turn_record(existing)

        branch = await self._session.scalar(select(BranchModel).where(BranchModel.id == bundle.branch_id))
        if branch is None:
            raise PersistenceNotFoundError(f"Branch {bundle.branch_id} does not exist.")
        if branch.playthrough_id != bundle.playthrough_id:
            raise PersistenceStaleHeadError("Branch does not belong to the supplied playthrough.")
        if branch.lifecycle != "active":
            raise PersistenceStaleHeadError("Cannot commit a turn to an abandoned branch.")
        if bundle.parent_turn_id is not None and bundle.parent_turn_id != branch.head_turn_id:
            raise PersistenceStaleHeadError("Turn parent is no longer the branch head.")
        parent_turn_id = bundle.parent_turn_id or branch.head_turn_id

        if branch.head_turn_id is None:
            playthrough = await self._session.scalar(select(PlaythroughModel).where(PlaythroughModel.id == bundle.playthrough_id))
            if playthrough is None:
                raise PersistenceNotFoundError(f"Playthrough {bundle.playthrough_id} does not exist.")
            expected_world_time_start = playthrough.world_clock_minutes
        else:
            head_turn = await self._session.scalar(select(TurnModel).where(TurnModel.id == branch.head_turn_id))
            if head_turn is None:
                raise PersistenceNotFoundError(f"Branch head turn {branch.head_turn_id} does not exist.")
            expected_world_time_start = head_turn.world_time_end
        if bundle.world_time_start != expected_world_time_start:
            raise PersistenceStaleHeadError("Turn world time does not match the branch head.")
        if bundle.duration_minutes < 0 or bundle.world_time_end != bundle.world_time_start + bundle.duration_minutes:
            raise PersistenceStaleHeadError("Turn world time range is inconsistent.")

        head_update = await self._session.execute(
            update(BranchModel)
            .where(
                BranchModel.id == bundle.branch_id,
                BranchModel.head_revision == bundle.base_revision,
                BranchModel.lifecycle == "active",
            )
            .values(head_revision=BranchModel.head_revision + 1, updated_at=utc_now())
        )
        if getattr(head_update, "rowcount", None) != 1:
            raise PersistenceStaleHeadError("Branch head revision has changed.")
        new_revision = bundle.base_revision + 1
        self._maybe_fail(fail_after_step, "head_revision")

        duplicate_turn = await self._session.scalar(select(TurnModel).where(TurnModel.id == bundle.turn_id))
        if duplicate_turn is not None:
            raise PersistenceIdempotencyConflictError("turn_id already exists.")
        now = utc_now()
        turn = TurnModel(
            id=bundle.turn_id,
            playthrough_id=bundle.playthrough_id,
            branch_id=bundle.branch_id,
            parent_turn_id=parent_turn_id,
            raw_input=bundle.raw_input,
            normalized_input=bundle.normalized_input,
            base_revision=bundle.base_revision,
            status="completed",
            final_narrative=bundle.final_narrative,
            approved_patch=dict(bundle.approved_patch),
            suggested_actions=[dict(item) for item in bundle.suggested_actions],
            world_time_start=bundle.world_time_start,
            duration_minutes=bundle.duration_minutes,
            world_time_end=bundle.world_time_end,
            turn_run_id=bundle.turn_run_id,
            schema_version=bundle.schema_version,
            created_at=now,
            updated_at=now,
        )
        self._session.add(turn)
        await self._session.flush()
        self._maybe_fail(fail_after_step, "turn")

        await self._insert_events(bundle)
        self._maybe_fail(fail_after_step, "events")
        await self._insert_claims(bundle)
        self._maybe_fail(fail_after_step, "knowledge")
        await self._insert_claim_links(bundle)
        await self._insert_observations_and_beliefs(bundle)
        self._maybe_fail(fail_after_step, "observations")
        await self._upsert_character_states(bundle)
        await self._upsert_relationships(bundle)
        self._maybe_fail(fail_after_step, "relationships")
        await self._insert_narrative(bundle)
        self._maybe_fail(fail_after_step, "narrative")
        await self._insert_derived_intents(bundle, new_revision)
        self._maybe_fail(fail_after_step, "outbox")

        await self._session.execute(
            update(BranchModel)
            .where(BranchModel.id == bundle.branch_id)
            .values(head_turn_id=bundle.turn_id, updated_at=utc_now())
        )
        await self._session.execute(
            update(PlaythroughModel)
            .where(PlaythroughModel.id == bundle.playthrough_id)
            .values(
                world_clock_minutes=bundle.world_time_end,
                **({"rng_state": deepcopy(bundle.rng_state)} if bundle.rng_state is not None else {}),
                updated_at=utc_now(),
            )
        )
        self._maybe_fail(fail_after_step, "head_update")
        await self._session.flush()
        return _turn_record(turn)

    @staticmethod
    def _maybe_fail(requested_step: str | None, step: str) -> None:
        if requested_step == step:
            raise InjectedCommitFailure(f"Injected failure after canonical commit step: {step}")

    async def _insert_events(self, bundle: CanonicalTurnBundle) -> None:
        for record in bundle.events:
            self._session.add(
                EventModel(
                    id=record.event_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    event_type=record.event_type,
                    world_time=record.world_time,
                    location_id=record.location_id,
                    payload=dict(record.payload),
                    salience=record.salience,
                    emotional_intensity=record.emotional_intensity,
                    cause_event_ids=list(record.cause_event_ids),
                    provenance=dict(record.provenance),
                    schema_version=record.schema_version,
                    created_at=utc_now(),
                )
            )
        await self._session.flush()
        for record in bundle.events:
            participants = (
                [(item, "actor") for item in record.actor_ids]
                + [(item, "target") for item in record.target_ids]
                + [(item, "witness") for item in record.witness_ids]
            )
            for participant_id, role in participants:
                self._session.add(
                    EventParticipantModel(
                        id=str(uuid4()),
                        event_id=record.event_id,
                        participant_id=participant_id,
                        role=role,
                    )
                )
        await self._session.flush()

    async def _insert_claims(self, bundle: CanonicalTurnBundle) -> None:
        for record in bundle.claims:
            self._session.add(
                KnowledgeClaimModel(
                    id=record.claim_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    claim_type=record.claim_type,
                    subject_id=record.subject_id,
                    predicate=record.predicate,
                    object_id=record.object_id,
                    typed_value=record.typed_value,
                    polarity=record.polarity,
                    qualifiers=dict(record.qualifiers),
                    valid_time_start=record.valid_time_start,
                    valid_time_end=record.valid_time_end,
                    branch_scope=record.branch_scope,
                    normalized_fingerprint=record.normalized_fingerprint,
                    schema_version=record.schema_version,
                    provenance=dict(record.provenance),
                    created_at=utc_now(),
                )
            )
        await self._session.flush()
        for record in bundle.canon_facts:
            self._session.add(
                CanonFactModel(
                    id=record.fact_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    claim_id=record.claim_id,
                    status=record.status,
                    source_event_or_rule=record.source_event_or_rule,
                    asserted_world_time=record.asserted_world_time,
                    asserted_turn=record.asserted_turn,
                    superseded_by=record.superseded_by,
                )
            )
        await self._session.flush()

    async def _insert_claim_links(self, bundle: CanonicalTurnBundle) -> None:
        for record in bundle.claim_links:
            self._session.add(
                ClaimLinkModel(
                    id=record.link_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    from_claim_id=record.from_claim_id,
                    to_claim_id=record.to_claim_id,
                    kind=record.kind,
                )
            )
        await self._session.flush()

    async def _insert_observations_and_beliefs(self, bundle: CanonicalTurnBundle) -> None:
        for record in bundle.observations:
            self._session.add(
                ObservationModel(
                    id=record.observation_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    observer_id=record.observer_id,
                    observed_claim_id=record.observed_claim_id,
                    source_event_id=record.source_event_id,
                    method=record.method,
                    world_time=record.world_time,
                    confidence=record.confidence,
                    distortion=record.distortion,
                    provenance=dict(record.provenance),
                )
            )
        for record in bundle.beliefs:
            evidence_count = sum(item.belief_id == record.belief_id for item in bundle.belief_evidence)
            self._session.add(
                BeliefModel(
                    id=record.belief_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    believer_id=record.believer_id,
                    claim_id=record.claim_id,
                    stance=record.stance,
                    confidence=record.confidence,
                    evidence_count=evidence_count,
                    branch_scope=record.branch_scope,
                    world_time=record.world_time,
                    source_reliability=record.source_reliability,
                    provenance=dict(record.provenance),
                )
            )
        await self._session.flush()
        for record in bundle.belief_evidence:
            self._session.add(
                BeliefEvidenceModel(
                    id=record.evidence_id,
                    belief_id=record.belief_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    owner_id=record.owner_id,
                    source_event_id=record.source_event_id,
                    claim_id=record.claim_id,
                    world_time=record.world_time,
                    method=record.method,
                    confidence=record.confidence,
                    provenance=dict(record.provenance),
                )
            )
        await self._session.flush()

    async def _upsert_character_states(self, bundle: CanonicalTurnBundle) -> None:
        for record in bundle.character_states:
            model = await self._session.scalar(
                select(CharacterStateModel).where(
                    CharacterStateModel.character_id == record.character_id,
                    CharacterStateModel.playthrough_id == bundle.playthrough_id,
                    CharacterStateModel.branch_id == bundle.branch_id,
                )
            )
            if model is None:
                model = CharacterStateModel(
                    id=str(uuid4()),
                    character_id=record.character_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    state=dict(record.state),
                    last_active_turn_id=record.last_active_turn_id or bundle.turn_id,
                    schema_version=record.schema_version,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                self._session.add(model)
            else:
                model.state = dict(record.state)
                model.last_active_turn_id = record.last_active_turn_id or bundle.turn_id
                model.updated_at = utc_now()
        await self._session.flush()

    async def _upsert_relationships(self, bundle: CanonicalTurnBundle) -> None:
        for record in bundle.relationships:
            model = await self._session.scalar(
                select(RelationshipModel).where(
                    RelationshipModel.playthrough_id == bundle.playthrough_id,
                    RelationshipModel.branch_id == bundle.branch_id,
                    RelationshipModel.source_id == record.source_id,
                    RelationshipModel.target_id == record.target_id,
                )
            )
            if model is None:
                model = RelationshipModel(
                    id=record.relationship_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    source_id=record.source_id,
                    target_id=record.target_id,
                    values=dict(record.values),
                    schema_version=record.schema_version,
                    updated_at=utc_now(),
                )
                self._session.add(model)
            else:
                model.values = dict(record.values)
                model.schema_version = record.schema_version
                model.updated_at = utc_now()
        await self._session.flush()
        for record in bundle.relationship_changes:
            existing_relationship = await self._session.scalar(
                select(RelationshipModel).where(RelationshipModel.id == record.relationship_id)
            )
            if existing_relationship is None:
                raise PersistenceNotFoundError(f"Relationship {record.relationship_id} does not exist for change log.")
            self._session.add(
                RelationshipChangeModel(
                    id=record.change_id,
                    relationship_id=existing_relationship.id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    dimension=record.dimension,
                    before=record.before,
                    proposed_delta=record.proposed_delta,
                    validated_delta=record.validated_delta,
                    after=record.after,
                    cause_event_id=record.cause_event_id,
                    reason=record.reason,
                    provenance=dict(record.provenance),
                )
            )
        await self._session.flush()

    async def _insert_narrative(self, bundle: CanonicalTurnBundle) -> None:
        for record in bundle.tensions:
            self._session.add(
                EmotionalTensionModel(
                    id=record.tension_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    observer_id=record.observer_id,
                    rival_id=record.rival_id,
                    focus_id=record.focus_id,
                    intensity=record.intensity,
                    payload=dict(record.payload),
                )
            )
        for record in bundle.threads:
            self._session.add(
                NarrativeThreadModel(
                    id=record.thread_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    status=record.status,
                    progress=record.progress,
                    urgency=record.urgency,
                    payload=dict(record.payload),
                )
            )
        for record in bundle.hooks:
            self._session.add(
                NarrativeHookModel(
                    id=record.hook_id,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    turn_id=bundle.turn_id,
                    status=record.status,
                    payload=dict(record.payload),
                )
            )
        await self._session.flush()

    async def _insert_derived_intents(self, bundle: CanonicalTurnBundle, revision: int) -> None:
        for job_type in bundle.derived_job_types:
            idempotency_key = f"{job_type}:{bundle.branch_id}:{bundle.turn_id}:{revision}"
            self._session.add(
                DerivedJobModel(
                    id=str(uuid4()),
                    idempotency_key=idempotency_key,
                    job_type=job_type,
                    playthrough_id=bundle.playthrough_id,
                    branch_id=bundle.branch_id,
                    source_turn_id=bundle.turn_id,
                    source_revision=revision,
                    payload={},
                    status="queued",
                    attempts=0,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
            )
        self._session.add(
            OutboxEventModel(
                id=str(uuid4()),
                idempotency_key=f"canonical-turn:{bundle.turn_id}",
                event_type="canonical_turn_committed",
                playthrough_id=bundle.playthrough_id,
                branch_id=bundle.branch_id,
                turn_id=bundle.turn_id,
                payload={"source_revision": revision},
                status="pending",
                created_at=utc_now(),
            )
        )
        await self._session.flush()

    async def _visible_turn_ids(self, branch_id: str) -> tuple[list[BranchRecord], list[str]]:
        ancestry = await self.get_branch_ancestry(branch_id)
        target = ancestry[-1]
        turn_ids: list[str] = []
        current_id = target.head_turn_id
        seen: set[str] = set()
        while current_id is not None:
            if current_id in seen:
                raise PersistenceNotFoundError(f"Turn ancestry cycle detected at {current_id}.")
            seen.add(current_id)
            turn = await self._session.scalar(select(TurnModel).where(TurnModel.id == current_id))
            if turn is None:
                raise PersistenceNotFoundError(f"Turn {current_id} does not exist.")
            turn_ids.append(turn.id)
            current_id = turn.parent_turn_id
        return ancestry, turn_ids

    async def list_visible_events(self, branch_id: str) -> list[EventRecord]:
        ancestry, turn_ids = await self._visible_turn_ids(branch_id)
        if not turn_ids:
            return []
        models = list(
            (
                await self._session.scalars(
                    select(EventModel)
                    .where(
                        EventModel.branch_id.in_([item.id for item in ancestry]),
                        EventModel.turn_id.in_(turn_ids),
                    )
                    .order_by(EventModel.world_time, EventModel.created_at, EventModel.id)
                )
            ).all()
        )
        if not models:
            return []
        participants = list(
            (
                await self._session.scalars(
                    select(EventParticipantModel).where(EventParticipantModel.event_id.in_([item.id for item in models]))
                )
            ).all()
        )
        by_event: dict[str, list[EventParticipantModel]] = {}
        for participant in participants:
            by_event.setdefault(participant.event_id, []).append(participant)
        return [_event_record(model, by_event.get(model.id, [])) for model in models]

    async def list_approved_patches(
        self,
        branch_id: str,
        *,
        after_revision: int = 0,
    ) -> list[tuple[int, dict[str, object]]]:
        ancestry, turn_ids = await self._visible_turn_ids(branch_id)
        if not turn_ids:
            return []
        models = list(
            (
                await self._session.scalars(
                    select(TurnModel).where(
                        TurnModel.branch_id.in_([item.id for item in ancestry]),
                        TurnModel.id.in_(turn_ids),
                        TurnModel.status == "completed",
                    )
                )
            ).all()
        )
        order = {turn_id: index for index, turn_id in enumerate(reversed(turn_ids))}
        models.sort(key=lambda item: order[item.id])
        if after_revision > 0:
            models = [item for item in models if item.branch_id == branch_id and item.base_revision + 1 > after_revision]
        return [(item.base_revision + 1, dict(item.approved_patch or {})) for item in models if item.approved_patch is not None]

    async def save_snapshot(self, snapshot: SnapshotRecord) -> None:
        if not snapshot.is_valid():
            raise PersistenceSnapshotError("Snapshot checksum does not match its payload.")
        branch = await self._session.scalar(select(BranchModel).where(BranchModel.id == snapshot.branch_id))
        if branch is None:
            raise PersistenceNotFoundError(f"Branch {snapshot.branch_id} does not exist.")
        if snapshot.source_revision > branch.head_revision:
            raise PersistenceSnapshotError("Snapshot source revision is ahead of the branch head.")
        self._session.add(
            SnapshotModel(
                id=snapshot.snapshot_id,
                playthrough_id=snapshot.playthrough_id,
                branch_id=snapshot.branch_id,
                source_turn_id=snapshot.source_turn_id,
                source_revision=snapshot.source_revision,
                world_clock_minutes=snapshot.world_clock_minutes,
                rng_state=deepcopy(snapshot.rng_state),
                state_payload=dict(snapshot.state_payload),
                checksum=snapshot.checksum,
                builder_version=snapshot.builder_version,
                schema_version=snapshot.schema_version,
                created_at=snapshot.created_at,
            )
        )
        await self._session.flush()

    async def load_latest_snapshot(self, branch_id: str) -> SnapshotRecord | None:
        branch = await self._session.scalar(select(BranchModel).where(BranchModel.id == branch_id))
        if branch is None:
            raise PersistenceNotFoundError(f"Branch {branch_id} does not exist.")
        models = list(
            (
                await self._session.scalars(
                    select(SnapshotModel)
                    .where(
                        SnapshotModel.branch_id == branch_id,
                        SnapshotModel.source_revision <= branch.head_revision,
                    )
                    .order_by(SnapshotModel.source_revision.desc(), SnapshotModel.created_at.desc())
                )
            ).all()
        )
        for model in models:
            record = _snapshot_record(model)
            if record.is_valid():
                return record
        return None

    async def enqueue_derived_job(self, job: DerivedJobRecord) -> DerivedJobRecord:
        existing = await self._session.scalar(
            select(DerivedJobModel).where(DerivedJobModel.idempotency_key == job.idempotency_key)
        )
        if existing is not None:
            return _derived_job_record(existing)
        self._session.add(
            DerivedJobModel(
                id=job.id,
                idempotency_key=job.idempotency_key,
                job_type=job.job_type,
                playthrough_id=job.playthrough_id,
                branch_id=job.branch_id,
                source_turn_id=job.source_turn_id,
                source_revision=job.source_revision,
                payload=dict(job.payload),
                status=job.status,
                attempts=job.attempts,
                last_error=job.last_error,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )
        await self._session.flush()
        return job

    async def list_derived_jobs(self, *, status: str | None = None) -> list[DerivedJobRecord]:
        statement = select(DerivedJobModel).order_by(DerivedJobModel.created_at, DerivedJobModel.id)
        if status is not None:
            statement = statement.where(DerivedJobModel.status == status)
        return [_derived_job_record(model) for model in (await self._session.scalars(statement)).all()]

    async def mark_derived_job(self, job_id: str, *, status: str, error: str | None = None) -> None:
        result = await self._session.execute(
            update(DerivedJobModel)
            .where(DerivedJobModel.id == job_id)
            .values(
                status=status,
                last_error=error,
                attempts=DerivedJobModel.attempts + 1,
                updated_at=utc_now(),
            )
        )
        if getattr(result, "rowcount", None) != 1:
            raise PersistenceNotFoundError(f"Derived job {job_id} does not exist.")
        await self._session.flush()

    async def reconcile_derived_jobs(self) -> int:
        turns = list((await self._session.scalars(select(TurnModel).where(TurnModel.status == "completed"))).all())
        created = 0
        for turn in turns:
            branch = await self._session.scalar(select(BranchModel).where(BranchModel.id == turn.branch_id))
            if branch is None:
                continue
            for job_type in ("snapshot", "summary", "embedding"):
                key = f"{job_type}:{turn.branch_id}:{turn.id}:{turn.base_revision + 1}"
                exists = await self._session.scalar(select(DerivedJobModel.id).where(DerivedJobModel.idempotency_key == key))
                if exists is None:
                    self._session.add(
                        DerivedJobModel(
                            id=str(uuid4()),
                            idempotency_key=key,
                            job_type=job_type,
                            playthrough_id=turn.playthrough_id,
                            branch_id=turn.branch_id,
                            source_turn_id=turn.id,
                            source_revision=turn.base_revision + 1,
                            payload={},
                            status="queued",
                            attempts=0,
                            created_at=utc_now(),
                            updated_at=utc_now(),
                        )
                    )
                    created += 1
        await self._session.flush()
        return created


__all__ = ["InjectedCommitFailure", "SqlAlchemyCanonicalRepository"]
