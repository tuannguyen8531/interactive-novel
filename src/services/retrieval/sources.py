"""Adapters from canonical persistence records to retrieval candidates."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from src.application.contracts.persistence import (
    BeliefRecord,
    EventRecord,
    KnowledgeClaimRecord,
    NarrativeHookRecord,
    NarrativeThreadRecord,
    ObservationRecord,
)
from src.application.contracts.retrieval import PUBLIC_OWNER, MemoryCandidate, MemoryKind


def _text_from_payload(payload: Mapping[str, Any], fallback: str) -> str:
    for key in ("text", "summary", "description", "narrative"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _visibility(provenance: Mapping[str, Any], payload: Mapping[str, Any] | None = None) -> str:
    source = payload if payload is not None else provenance
    value = source.get("visibility", "public")
    return str(value) if value is not None else "public"


def event_to_candidate(record: EventRecord) -> MemoryCandidate:
    payload = dict(record.payload)
    fallback = record.event_type.replace("_", " ")
    return MemoryCandidate(
        source_id=record.event_id,
        kind=MemoryKind.EVENT,
        playthrough_id=record.playthrough_id,
        branch_id=record.branch_id,
        world_time=record.world_time,
        text=_text_from_payload(payload, fallback),
        owner_id=str(payload.get("owner_id", PUBLIC_OWNER)),
        visibility=_visibility({}, payload),
        source_event_id=record.event_id,
        branch_scope=str(payload.get("branch_scope", record.branch_id)),
        entity_ids=tuple(dict.fromkeys((*record.actor_ids, *record.target_ids, *record.witness_ids))),
        goal_ids=_tuple_strings(payload.get("goal_ids")),
        thread_ids=_tuple_strings(payload.get("thread_ids")),
        salience=record.salience,
        emotional_intensity=record.emotional_intensity,
        payload=payload,
        provenance=dict(record.provenance),
    )


def claim_to_candidate(record: KnowledgeClaimRecord) -> MemoryCandidate:
    value = (
        record.object_id
        if record.object_id is not None
        else json.dumps(
            record.typed_value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    text = f"{record.subject_id} {record.predicate} {value}"
    provenance = dict(record.provenance)
    return MemoryCandidate(
        source_id=record.claim_id,
        kind=MemoryKind.CLAIM,
        playthrough_id=record.playthrough_id,
        branch_id=record.branch_id,
        world_time=record.valid_time_start,
        text=text,
        owner_id=str(provenance.get("owner_id", PUBLIC_OWNER)),
        visibility=_visibility(provenance),
        source_event_id=str(provenance["source_event_id"]) if provenance.get("source_event_id") else None,
        claim_id=record.claim_id,
        normalized_fingerprint=record.normalized_fingerprint,
        branch_scope=record.branch_scope,
        valid_time_start=record.valid_time_start,
        valid_time_end=record.valid_time_end,
        entity_ids=tuple(item for item in (record.subject_id, record.object_id) if item),
        goal_ids=_tuple_strings(record.qualifiers.get("goal_ids")),
        thread_ids=_tuple_strings(record.qualifiers.get("thread_ids")),
        predicate=record.predicate,
        subject_id=record.subject_id,
        object_id=record.object_id,
        typed_value=record.typed_value,
        payload={
            "claim_type": record.claim_type,
            "predicate": record.predicate,
            "polarity": record.polarity,
            "qualifiers": dict(record.qualifiers),
        },
        provenance=provenance,
    )


def observation_to_candidate(record: ObservationRecord) -> MemoryCandidate:
    provenance = dict(record.provenance)
    return MemoryCandidate(
        source_id=record.observation_id,
        kind=MemoryKind.OBSERVATION,
        playthrough_id=record.playthrough_id,
        branch_id=record.branch_id,
        world_time=record.world_time,
        text=f"{record.observer_id} {record.method} claim {record.observed_claim_id}",
        owner_id=record.observer_id,
        visibility="owner",
        source_event_id=record.source_event_id,
        claim_id=record.observed_claim_id,
        branch_scope=record.branch_id,
        entity_ids=(record.observer_id,),
        salience=record.confidence,
        payload={"method": record.method, "confidence": record.confidence, "distortion": record.distortion},
        provenance=provenance,
    )


def belief_to_candidate(record: BeliefRecord) -> MemoryCandidate:
    provenance = dict(record.provenance)
    source_event_id = provenance.get("source_event_id") or provenance.get("event_id")
    return MemoryCandidate(
        source_id=record.belief_id,
        kind=MemoryKind.BELIEF,
        playthrough_id=record.playthrough_id,
        branch_id=record.branch_id,
        world_time=record.world_time,
        text=f"{record.believer_id} believes {record.claim_id} ({record.stance})",
        owner_id=record.believer_id,
        visibility="owner",
        source_event_id=str(source_event_id) if source_event_id else None,
        claim_id=record.claim_id,
        branch_scope=record.branch_scope,
        entity_ids=(record.believer_id,),
        salience=record.confidence,
        payload={
            "stance": record.stance,
            "confidence": record.confidence,
            "source_reliability": record.source_reliability,
        },
        provenance=provenance,
    )


def thread_to_candidate(record: NarrativeThreadRecord) -> MemoryCandidate:
    payload = dict(record.payload)
    return MemoryCandidate(
        source_id=record.thread_id,
        kind=MemoryKind.THREAD,
        playthrough_id=record.playthrough_id,
        branch_id=record.branch_id,
        world_time=int(payload.get("world_time", 0)),
        text=_text_from_payload(payload, f"thread {record.thread_id} is {record.status}"),
        owner_id=str(payload.get("owner_id", PUBLIC_OWNER)),
        visibility=str(payload.get("visibility", "public")),
        branch_scope=record.branch_id,
        entity_ids=_tuple_strings(payload.get("participant_ids")),
        goal_ids=_tuple_strings(payload.get("goal_ids")),
        thread_ids=(record.thread_id,),
        salience=record.urgency,
        emotional_intensity=float(payload.get("emotional_intensity", 0.0)),
        payload=payload,
    )


def hook_to_candidate(record: NarrativeHookRecord) -> MemoryCandidate:
    payload = dict(record.payload)
    thread_id = payload.get("thread_id")
    return MemoryCandidate(
        source_id=record.hook_id,
        kind=MemoryKind.HOOK,
        playthrough_id=record.playthrough_id,
        branch_id=record.branch_id,
        world_time=int(payload.get("world_time", 0)),
        text=_text_from_payload(payload, f"hook {record.hook_id} is {record.status}"),
        owner_id=str(payload.get("owner_id", PUBLIC_OWNER)),
        visibility=str(payload.get("visibility", "public")),
        branch_scope=record.branch_id,
        entity_ids=_tuple_strings(payload.get("participant_ids")),
        goal_ids=_tuple_strings(payload.get("goal_ids")),
        thread_ids=(str(thread_id),) if isinstance(thread_id, str) and thread_id.strip() else (),
        salience=float(payload.get("salience", 0.6)),
        emotional_intensity=float(payload.get("emotional_intensity", 0.0)),
        payload=payload,
    )


def summary_to_candidate(
    *,
    source_id: str,
    playthrough_id: str,
    branch_id: str,
    world_time: int,
    text: str,
    payload: Mapping[str, Any],
) -> MemoryCandidate:
    """Adapt an episodic summary while retaining its canonical source IDs."""
    data = dict(payload)
    return MemoryCandidate(
        source_id=source_id,
        kind=MemoryKind.SUMMARY,
        playthrough_id=playthrough_id,
        branch_id=branch_id,
        world_time=world_time,
        text=text,
        owner_id="public",
        visibility="public",
        branch_scope=branch_id,
        entity_ids=_tuple_strings(data.get("entity_ids")),
        goal_ids=_tuple_strings(data.get("goal_ids")),
        thread_ids=_tuple_strings(data.get("thread_ids")),
        salience=float(data.get("salience", 0.75)),
        payload=data,
        provenance={"derived": True, "canonical_source_ids": list(data.get("source_ids", []))},
    )


__all__ = [
    "belief_to_candidate",
    "claim_to_candidate",
    "event_to_candidate",
    "hook_to_candidate",
    "observation_to_candidate",
    "summary_to_candidate",
    "thread_to_candidate",
]
