"""SQLite adapters for canonical retrieval sources and derived artifacts."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from struct import pack, unpack

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.contracts.persistence import (
    BeliefRecord,
    EventRecord,
    KnowledgeClaimRecord,
    NarrativeHookRecord,
    NarrativeThreadRecord,
    ObservationRecord,
)
from src.application.contracts.retrieval import (
    EmbeddingMetadata,
    EmbeddingRecord,
    MemoryCandidate,
    RetrievalScope,
    RetrievalTrace,
)
from src.services.retrieval.sources import (
    belief_to_candidate,
    claim_to_candidate,
    event_to_candidate,
    hook_to_candidate,
    observation_to_candidate,
    summary_to_candidate,
    thread_to_candidate,
)

from .models import (
    BeliefModel,
    DerivedArtifactModel,
    EventModel,
    EventParticipantModel,
    KnowledgeClaimModel,
    MemoryEmbeddingModel,
    NarrativeHookModel,
    NarrativeThreadModel,
    ObservationModel,
    RetrievalTraceModel,
)
from .visibility import resolve_visible_branch_scope


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _embedding_id(record: EmbeddingRecord) -> str:
    metadata = record.metadata
    identity = ":".join(
        (
            metadata.source_id,
            metadata.model,
            metadata.embedding_version,
            metadata.content_hash,
        )
    )
    return sha256(identity.encode("utf-8")).hexdigest()


def _serialize_vector(vector: tuple[float, ...]) -> bytes:
    return pack(f"!{len(vector)}f", *vector)


def _deserialize_vector(vector: bytes, dimensions: int) -> tuple[float, ...]:
    expected_size = dimensions * 4
    if len(vector) != expected_size:
        raise ValueError("Stored embedding vector length does not match metadata dimensions.")
    return tuple(unpack(f"!{dimensions}f", vector))


class SqlAlchemyEmbeddingStore:
    """Durable derived embedding store with source-hash invalidation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: EmbeddingRecord) -> None:
        metadata = record.metadata
        model = await self._session.scalar(
            select(MemoryEmbeddingModel).where(
                MemoryEmbeddingModel.source_id == metadata.source_id,
                MemoryEmbeddingModel.model == metadata.model,
                MemoryEmbeddingModel.embedding_version == metadata.embedding_version,
                MemoryEmbeddingModel.content_hash == metadata.content_hash,
            )
        )
        values = {
            "source_id": metadata.source_id,
            "source_kind": str(metadata.source_kind),
            "playthrough_id": metadata.playthrough_id,
            "branch_id": metadata.branch_id,
            "model": metadata.model,
            "dimensions": metadata.dimensions,
            "embedding_version": metadata.embedding_version,
            "content_hash": metadata.content_hash,
            "vector": _serialize_vector(record.vector),
            "created_at": metadata.created_at,
        }
        if model is None:
            self._session.add(MemoryEmbeddingModel(id=_embedding_id(record), **values))
        else:
            for key, value in values.items():
                setattr(model, key, value)
        await self._session.flush()

    async def get(
        self,
        *,
        source_id: str,
        content_hash: str,
        model: str,
        embedding_version: str,
    ) -> EmbeddingRecord | None:
        stored = await self._session.scalar(
            select(MemoryEmbeddingModel).where(
                MemoryEmbeddingModel.source_id == source_id,
                MemoryEmbeddingModel.content_hash == content_hash,
                MemoryEmbeddingModel.model == model,
                MemoryEmbeddingModel.embedding_version == embedding_version,
            )
        )
        if stored is None:
            return None
        metadata = EmbeddingMetadata(
            source_id=stored.source_id,
            source_kind=stored.source_kind,
            playthrough_id=stored.playthrough_id,
            branch_id=stored.branch_id,
            model=stored.model,
            dimensions=stored.dimensions,
            embedding_version=stored.embedding_version,
            content_hash=stored.content_hash,
            created_at=_as_utc(stored.created_at),
        )
        return EmbeddingRecord(
            metadata=metadata,
            vector=_deserialize_vector(stored.vector, stored.dimensions),
        )


class SqlAlchemyRetrievalTraceStore:
    """Persist only retrieval IDs, scope and score metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, trace: RetrievalTrace) -> None:
        existing = await self._session.scalar(select(RetrievalTraceModel).where(RetrievalTraceModel.id == trace.trace_id))
        if existing is None:
            self._session.add(
                RetrievalTraceModel(
                    id=trace.trace_id,
                    query_id=trace.query_id,
                    phase=str(trace.phase),
                    playthrough_id=trace.scope.playthrough_id,
                    branch_id=trace.scope.branch_id,
                    owner_id=trace.scope.owner_id,
                    world_time=trace.scope.world_time,
                    payload=trace.as_dict(),
                    created_at=trace.created_at,
                )
            )
        else:
            existing.payload = trace.as_dict()
        await self._session.flush()


class SqlAlchemyRetrievalRepository(SqlAlchemyEmbeddingStore):
    """Read canonical candidates and expose derived stores through ports."""

    def __init__(self, session: AsyncSession) -> None:
        SqlAlchemyEmbeddingStore.__init__(self, session)
        self._session = session
        self.trace_store = SqlAlchemyRetrievalTraceStore(session)

    async def save_trace(self, trace: RetrievalTrace) -> None:
        await self.trace_store.save(trace)

    async def list_candidates(self, scope: RetrievalScope) -> tuple[MemoryCandidate, ...]:
        visible = await resolve_visible_branch_scope(self._session, scope.branch_id)
        requested_branch_ids = set(scope.allowed_branch_ids)
        branch_ids = tuple(branch_id for branch_id in visible.branch_ids if branch_id in requested_branch_ids)
        turn_ids = visible.turn_ids
        if not branch_ids or not turn_ids:
            return ()

        events = list(
            (
                await self._session.scalars(
                    select(EventModel).where(
                        EventModel.playthrough_id == scope.playthrough_id,
                        EventModel.branch_id.in_(branch_ids),
                        EventModel.turn_id.in_(turn_ids),
                        EventModel.world_time <= scope.world_time,
                    )
                )
            ).all()
        )
        event_ids = [item.id for item in events]
        participants = (
            list(
                (
                    await self._session.scalars(
                        select(EventParticipantModel).where(EventParticipantModel.event_id.in_(event_ids))
                    )
                ).all()
            )
            if event_ids
            else []
        )
        participant_map: dict[str, list[EventParticipantModel]] = defaultdict(list)
        for participant in participants:
            participant_map[participant.event_id].append(participant)

        candidates: list[MemoryCandidate] = []
        for event in events:
            event_participants = participant_map[event.id]
            candidates.append(
                event_to_candidate(
                    EventRecord(
                        event_id=event.id,
                        playthrough_id=event.playthrough_id,
                        branch_id=event.branch_id,
                        turn_id=event.turn_id,
                        event_type=event.event_type,
                        world_time=event.world_time,
                        location_id=event.location_id,
                        actor_ids=tuple(item.participant_id for item in event_participants if item.role == "actor"),
                        target_ids=tuple(item.participant_id for item in event_participants if item.role == "target"),
                        witness_ids=tuple(item.participant_id for item in event_participants if item.role == "witness"),
                        payload=dict(event.payload),
                        salience=event.salience,
                        emotional_intensity=event.emotional_intensity,
                        cause_event_ids=tuple(event.cause_event_ids),
                        provenance=dict(event.provenance),
                        schema_version=event.schema_version,
                    )
                )
            )

        claims = list(
            (
                await self._session.scalars(
                    select(KnowledgeClaimModel).where(
                        KnowledgeClaimModel.playthrough_id == scope.playthrough_id,
                        KnowledgeClaimModel.branch_id.in_(branch_ids),
                        KnowledgeClaimModel.turn_id.in_(turn_ids),
                        KnowledgeClaimModel.valid_time_start <= scope.world_time,
                        (KnowledgeClaimModel.valid_time_end.is_(None) | (KnowledgeClaimModel.valid_time_end >= scope.world_time)),
                    )
                )
            ).all()
        )
        candidates.extend(
            claim_to_candidate(
                KnowledgeClaimRecord(
                    claim_id=claim.id,
                    playthrough_id=claim.playthrough_id,
                    branch_id=claim.branch_id,
                    turn_id=claim.turn_id,
                    claim_type=claim.claim_type,
                    subject_id=claim.subject_id,
                    predicate=claim.predicate,
                    object_id=claim.object_id,
                    typed_value=claim.typed_value,
                    polarity=claim.polarity,
                    qualifiers=dict(claim.qualifiers),
                    valid_time_start=claim.valid_time_start,
                    valid_time_end=claim.valid_time_end,
                    branch_scope=claim.branch_scope,
                    normalized_fingerprint=claim.normalized_fingerprint,
                    schema_version=claim.schema_version,
                    provenance=dict(claim.provenance),
                )
            )
            for claim in claims
        )

        observations = list(
            (
                await self._session.scalars(
                    select(ObservationModel).where(
                        ObservationModel.playthrough_id == scope.playthrough_id,
                        ObservationModel.branch_id.in_(branch_ids),
                        ObservationModel.turn_id.in_(turn_ids),
                        ObservationModel.world_time <= scope.world_time,
                    )
                )
            ).all()
        )
        candidates.extend(
            observation_to_candidate(
                ObservationRecord(
                    observation_id=observation.id,
                    playthrough_id=observation.playthrough_id,
                    branch_id=observation.branch_id,
                    turn_id=observation.turn_id,
                    observer_id=observation.observer_id,
                    observed_claim_id=observation.observed_claim_id,
                    source_event_id=observation.source_event_id,
                    method=observation.method,
                    world_time=observation.world_time,
                    confidence=observation.confidence,
                    distortion=observation.distortion,
                    provenance=dict(observation.provenance),
                )
            )
            for observation in observations
        )

        beliefs = list(
            (
                await self._session.scalars(
                    select(BeliefModel).where(
                        BeliefModel.playthrough_id == scope.playthrough_id,
                        BeliefModel.branch_id.in_(branch_ids),
                        BeliefModel.turn_id.in_(turn_ids),
                        BeliefModel.world_time <= scope.world_time,
                    )
                )
            ).all()
        )
        candidates.extend(
            belief_to_candidate(
                BeliefRecord(
                    belief_id=belief.id,
                    playthrough_id=belief.playthrough_id,
                    branch_id=belief.branch_id,
                    turn_id=belief.turn_id,
                    believer_id=belief.believer_id,
                    claim_id=belief.claim_id,
                    stance=belief.stance,
                    confidence=belief.confidence,
                    branch_scope=belief.branch_scope,
                    world_time=belief.world_time,
                    source_reliability=belief.source_reliability,
                    provenance=dict(belief.provenance),
                )
            )
            for belief in beliefs
        )

        threads = list(
            (
                await self._session.scalars(
                    select(NarrativeThreadModel).where(
                        NarrativeThreadModel.playthrough_id == scope.playthrough_id,
                        NarrativeThreadModel.branch_id.in_(branch_ids),
                        NarrativeThreadModel.turn_id.in_(turn_ids),
                    )
                )
            ).all()
        )
        candidates.extend(
            thread_to_candidate(
                NarrativeThreadRecord(
                    thread_id=thread.id,
                    playthrough_id=thread.playthrough_id,
                    branch_id=thread.branch_id,
                    turn_id=thread.turn_id,
                    status=thread.status,
                    progress=thread.progress,
                    urgency=thread.urgency,
                    payload=dict(thread.payload),
                )
            )
            for thread in threads
        )

        hooks = list(
            (
                await self._session.scalars(
                    select(NarrativeHookModel).where(
                        NarrativeHookModel.playthrough_id == scope.playthrough_id,
                        NarrativeHookModel.branch_id.in_(branch_ids),
                        NarrativeHookModel.turn_id.in_(turn_ids),
                    )
                )
            ).all()
        )
        candidates.extend(
            hook_to_candidate(
                NarrativeHookRecord(
                    hook_id=hook.id,
                    playthrough_id=hook.playthrough_id,
                    branch_id=hook.branch_id,
                    turn_id=hook.turn_id,
                    status=hook.status,
                    payload=dict(hook.payload),
                )
            )
            for hook in hooks
        )
        summaries = list(
            (
                await self._session.scalars(
                    select(DerivedArtifactModel).where(
                        DerivedArtifactModel.playthrough_id == scope.playthrough_id,
                        DerivedArtifactModel.branch_id.in_(branch_ids),
                        DerivedArtifactModel.source_turn_id.in_(turn_ids),
                        DerivedArtifactModel.artifact_type == "episodic_summary",
                        DerivedArtifactModel.status == "fresh",
                    )
                )
            ).all()
        )
        candidates.extend(
            summary_to_candidate(
                source_id=artifact.id,
                playthrough_id=artifact.playthrough_id,
                branch_id=artifact.branch_id,
                world_time=int(artifact.payload.get("end_world_time", scope.world_time)),
                text=str(artifact.payload.get("text", "")),
                payload={**dict(artifact.payload), "source_revision": artifact.source_revision},
            )
            for artifact in summaries
            if str(artifact.payload.get("text", "")).strip()
        )
        return tuple(candidates)


__all__ = [
    "SqlAlchemyEmbeddingStore",
    "SqlAlchemyRetrievalRepository",
    "SqlAlchemyRetrievalTraceStore",
]
