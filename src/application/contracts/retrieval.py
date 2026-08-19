"""Contracts for perspective-aware context assembly and memory retrieval.

Retrieval is a derived/read concern.  These records deliberately carry enough
scope information for a service to enforce playthrough, branch, time and owner
boundaries before ranking a candidate.  They do not grant authority to mutate
canon or game state.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from typing import Any
from uuid import uuid4

from .ai import KnowledgeClaimProposal, KnowledgeRequirement, StateOperation, ValidationQuery

PUBLIC_OWNER = "public"


class MemoryKind(StrEnum):
    EVENT = "event"
    CLAIM = "claim"
    OBSERVATION = "observation"
    BELIEF = "belief"
    THREAD = "thread"
    HOOK = "hook"
    STATE = "state"
    SUMMARY = "summary"


class RetrievalPhase(StrEnum):
    INITIAL = "initial"
    TARGETED = "targeted"


def content_hash(text: str) -> str:
    """Return the stable source hash used to invalidate derived embeddings."""
    return sha256(text.encode("utf-8")).hexdigest()


def canonical_value(value: Any) -> str:
    """Serialize a typed value deterministically for exact claim lookup."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    """Hard visibility boundary applied before any ranking or embedding step."""

    playthrough_id: str
    branch_id: str
    world_time: int
    owner_id: str | None = None
    branch_ancestry: tuple[str, ...] = ()
    include_public: bool = True

    def __post_init__(self) -> None:
        if not self.playthrough_id.strip() or not self.branch_id.strip():
            raise ValueError("Retrieval scope requires playthrough and branch IDs.")
        if self.world_time < 0:
            raise ValueError("Retrieval world time cannot be negative.")
        ancestry = tuple(item.strip() for item in self.branch_ancestry if item.strip())
        if not ancestry:
            ancestry = (self.branch_id,)
        if self.branch_id not in ancestry:
            ancestry = (*ancestry, self.branch_id)
        object.__setattr__(self, "branch_ancestry", ancestry)
        if self.owner_id is not None and not self.owner_id.strip():
            raise ValueError("Retrieval owner ID cannot be blank.")

    @property
    def allowed_branch_ids(self) -> frozenset[str]:
        return frozenset(self.branch_ancestry)


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    """A canonical or perspective-owned record eligible for derived retrieval."""

    source_id: str
    kind: MemoryKind | str
    playthrough_id: str
    branch_id: str
    world_time: int
    text: str
    owner_id: str | None = PUBLIC_OWNER
    visibility: str = "public"
    source_event_id: str | None = None
    claim_id: str | None = None
    normalized_fingerprint: str | None = None
    branch_scope: str = "public"
    valid_time_start: int | None = None
    valid_time_end: int | None = None
    entity_ids: tuple[str, ...] = ()
    goal_ids: tuple[str, ...] = ()
    thread_ids: tuple[str, ...] = ()
    predicate: str | None = None
    subject_id: str | None = None
    object_id: str | None = None
    typed_value: Any = None
    salience: float = 0.5
    emotional_intensity: float = 0.0
    payload: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.playthrough_id.strip() or not self.branch_id.strip():
            raise ValueError("Memory candidate identity and scope are required.")
        if self.world_time < 0:
            raise ValueError("Memory candidate world time cannot be negative.")
        if not self.text.strip():
            raise ValueError("Memory candidate text cannot be empty.")
        if not 0.0 <= self.salience <= 1.0 or not 0.0 <= self.emotional_intensity <= 1.0:
            raise ValueError("Memory candidate scores must be between 0 and 1.")
        if self.valid_time_start is not None and self.valid_time_start < 0:
            raise ValueError("Memory candidate valid time cannot be negative.")
        if self.valid_time_end is not None and (
            self.valid_time_end < 0 or (self.valid_time_start is not None and self.valid_time_end < self.valid_time_start)
        ):
            raise ValueError("Memory candidate valid time range is invalid.")
        object.__setattr__(self, "kind", MemoryKind(self.kind))
        object.__setattr__(self, "entity_ids", tuple(dict.fromkeys(item for item in self.entity_ids if item.strip())))
        object.__setattr__(self, "goal_ids", tuple(dict.fromkeys(item for item in self.goal_ids if item.strip())))
        object.__setattr__(self, "thread_ids", tuple(dict.fromkeys(item for item in self.thread_ids if item.strip())))
        object.__setattr__(self, "payload", dict(self.payload))
        object.__setattr__(self, "provenance", dict(self.provenance))

    @property
    def effective_source_event_id(self) -> str | None:
        return self.source_event_id or self.provenance.get("source_event_id") or self.provenance.get("event_id")

    @property
    def search_text(self) -> str:
        """Text used for lexical matching without exposing unfiltered data."""
        return self.text


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """Normalized query used by both initial and targeted retrieval."""

    query_id: str = field(default_factory=lambda: str(uuid4()))
    phase: RetrievalPhase | str = RetrievalPhase.INITIAL
    query_text: str = ""
    entity_ids: tuple[str, ...] = ()
    goal_ids: tuple[str, ...] = ()
    thread_ids: tuple[str, ...] = ()
    target_claim_ids: tuple[str, ...] = ()
    fingerprint: str | None = None
    subject_id: str | None = None
    predicate: str | None = None
    object_id: str | None = None
    typed_value: Any = None
    limit: int = 20
    scope: RetrievalScope | None = None

    def __post_init__(self) -> None:
        if not self.query_id.strip():
            raise ValueError("Retrieval query ID cannot be blank.")
        if self.limit <= 0:
            raise ValueError("Retrieval query limit must be positive.")
        object.__setattr__(self, "phase", RetrievalPhase(self.phase))
        for name in ("entity_ids", "goal_ids", "thread_ids", "target_claim_ids"):
            object.__setattr__(self, name, tuple(dict.fromkeys(item for item in getattr(self, name) if item.strip())))


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    recency: float
    salience: float
    emotional_intensity: float
    entity_match: float
    goal_match: float
    thread_match: float
    lexical_match: float
    exact_match: float
    total: float

    def as_dict(self) -> dict[str, float]:
        return {
            "recency": self.recency,
            "salience": self.salience,
            "emotional_intensity": self.emotional_intensity,
            "entity_match": self.entity_match,
            "goal_match": self.goal_match,
            "thread_match": self.thread_match,
            "lexical_match": self.lexical_match,
            "exact_match": self.exact_match,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    candidate: MemoryCandidate
    score: ScoreBreakdown
    match_reasons: tuple[str, ...] = ()
    embedding_score: float | None = None

    @property
    def source_id(self) -> str:
        return self.candidate.source_id


@dataclass(frozen=True, slots=True)
class ContextEntry:
    source_id: str
    kind: MemoryKind | str
    text: str
    world_time: int
    owner_id: str | None
    score: float
    token_estimate: int
    match_reasons: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    goal_ids: tuple[str, ...] = ()
    thread_ids: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_hit(cls, hit: RetrievalHit, *, token_estimate: int) -> ContextEntry:
        candidate = hit.candidate
        return cls(
            source_id=candidate.source_id,
            kind=candidate.kind,
            text=candidate.text,
            world_time=candidate.world_time,
            owner_id=candidate.owner_id,
            score=hit.score.total,
            token_estimate=token_estimate,
            match_reasons=hit.match_reasons,
            entity_ids=candidate.entity_ids,
            goal_ids=candidate.goal_ids,
            thread_ids=candidate.thread_ids,
            payload=dict(candidate.payload),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": str(self.kind),
            "text": self.text,
            "world_time": self.world_time,
            "owner_id": self.owner_id,
            "score": self.score,
            "token_estimate": self.token_estimate,
            "match_reasons": list(self.match_reasons),
            "entity_ids": list(self.entity_ids),
            "goal_ids": list(self.goal_ids),
            "thread_ids": list(self.thread_ids),
            "payload": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class InitialContextRequest:
    run_id: str
    role: str
    scope: RetrievalScope
    query_text: str = ""
    entity_ids: tuple[str, ...] = ()
    goal_ids: tuple[str, ...] = ()
    thread_ids: tuple[str, ...] = ()
    token_budget: int = 2_000
    max_items: int = 40
    recent_event_limit: int = 8
    include_kinds: tuple[MemoryKind | str, ...] = ()

    def __post_init__(self) -> None:
        if not self.run_id.strip() or not self.role.strip():
            raise ValueError("Initial context request requires run ID and role.")
        if self.token_budget <= 0 or self.max_items <= 0 or self.recent_event_limit < 0:
            raise ValueError("Initial context request limits are invalid.")
        object.__setattr__(self, "entity_ids", tuple(dict.fromkeys(item for item in self.entity_ids if item.strip())))
        object.__setattr__(self, "goal_ids", tuple(dict.fromkeys(item for item in self.goal_ids if item.strip())))
        object.__setattr__(self, "thread_ids", tuple(dict.fromkeys(item for item in self.thread_ids if item.strip())))
        object.__setattr__(self, "include_kinds", tuple(MemoryKind(item) for item in self.include_kinds))


@dataclass(frozen=True, slots=True)
class InitialContextManifest:
    """Perspective-safe context envelope passed to a logical AI role."""

    manifest_id: str
    run_id: str
    role: str
    scope: RetrievalScope
    entries: tuple[ContextEntry, ...]
    token_budget: int
    estimated_tokens: int
    retrieval_trace_ids: tuple[str, ...] = ()
    schema_version: str = "initial-context-manifest-1"
    embedding_model: str | None = None
    embedding_version: str | None = None

    @classmethod
    def new(
        cls,
        *,
        run_id: str,
        role: str,
        scope: RetrievalScope,
        entries: tuple[ContextEntry, ...],
        token_budget: int,
        estimated_tokens: int,
        retrieval_trace_ids: tuple[str, ...] = (),
        embedding_model: str | None = None,
        embedding_version: str | None = None,
    ) -> InitialContextManifest:
        return cls(
            manifest_id=str(uuid4()),
            run_id=run_id,
            role=role,
            scope=scope,
            entries=entries,
            token_budget=token_budget,
            estimated_tokens=estimated_tokens,
            retrieval_trace_ids=retrieval_trace_ids,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )

    def as_context(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "role": self.role,
            "scope": {
                "playthrough_id": self.scope.playthrough_id,
                "branch_id": self.scope.branch_id,
                "branch_ancestry": list(self.scope.branch_ancestry),
                "world_time": self.scope.world_time,
                "owner_id": self.scope.owner_id,
            },
            "entries": [entry.as_dict() for entry in self.entries],
            "token_budget": self.token_budget,
            "estimated_tokens": self.estimated_tokens,
            "retrieval_trace_ids": list(self.retrieval_trace_ids),
            "embedding_model": self.embedding_model,
            "embedding_version": self.embedding_version,
        }


@dataclass(frozen=True, slots=True)
class EmbeddingMetadata:
    source_id: str
    source_kind: MemoryKind | str
    playthrough_id: str
    branch_id: str
    model: str
    dimensions: int
    embedding_version: str
    content_hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.model.strip() or not self.embedding_version.strip():
            raise ValueError("Embedding metadata requires source, model and version.")
        if self.dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive.")
        object.__setattr__(self, "source_kind", MemoryKind(self.source_kind))


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    metadata: EmbeddingMetadata
    vector: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.vector) != self.metadata.dimensions:
            raise ValueError("Embedding vector length does not match metadata dimensions.")
        if not all(isfinite(value) for value in self.vector):
            raise ValueError("Embedding vector must contain finite values.")


@dataclass(frozen=True, slots=True)
class RetrievalTraceHit:
    source_id: str
    score: ScoreBreakdown
    selected: bool
    dropped_reason: str | None = None
    embedding_score: float | None = None


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    """Safe audit record; it contains IDs and scores, not raw prompts/outputs."""

    trace_id: str
    query_id: str
    phase: RetrievalPhase | str
    scope: RetrievalScope
    candidate_count: int
    hard_filtered_count: int
    hits: tuple[RetrievalTraceHit, ...]
    token_budget: int
    estimated_tokens: int
    embedding_enabled: bool = False
    embedding_model: str | None = None
    embedding_version: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "phase", RetrievalPhase(self.phase))

    def as_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "query_id": self.query_id,
            "phase": str(self.phase),
            "scope": {
                "playthrough_id": self.scope.playthrough_id,
                "branch_id": self.scope.branch_id,
                "branch_ancestry": list(self.scope.branch_ancestry),
                "world_time": self.scope.world_time,
                "owner_id": self.scope.owner_id,
            },
            "candidate_count": self.candidate_count,
            "hard_filtered_count": self.hard_filtered_count,
            "hits": [
                {
                    "source_id": hit.source_id,
                    "score": hit.score.as_dict(),
                    "embedding_score": hit.embedding_score,
                    "selected": hit.selected,
                    "dropped_reason": hit.dropped_reason,
                }
                for hit in self.hits
            ],
            "token_budget": self.token_budget,
            "estimated_tokens": self.estimated_tokens,
            "embedding_enabled": self.embedding_enabled,
            "embedding_model": self.embedding_model,
            "embedding_version": self.embedding_version,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ClaimExtractionResult:
    """Deterministic bridge from typed AI proposals to validation queries."""

    proposed_claims: tuple[KnowledgeClaimProposal, ...]
    proposed_mutations: tuple[StateOperation, ...]
    knowledge_requirements: tuple[KnowledgeRequirement, ...]
    validation_queries: tuple[ValidationQuery, ...]
    claim_to_mutation: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


__all__ = [
    "PUBLIC_OWNER",
    "ClaimExtractionResult",
    "ContextEntry",
    "EmbeddingMetadata",
    "EmbeddingRecord",
    "InitialContextManifest",
    "InitialContextRequest",
    "MemoryCandidate",
    "MemoryKind",
    "RetrievalHit",
    "RetrievalPhase",
    "RetrievalQuery",
    "RetrievalScope",
    "RetrievalTrace",
    "RetrievalTraceHit",
    "ScoreBreakdown",
    "canonical_value",
    "content_hash",
]
