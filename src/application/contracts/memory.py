"""Persistence-neutral records produced by derived memory jobs.

These records are intentionally non-authoritative.  They point back to
canonical source IDs and may be discarded and rebuilt without changing a
playthrough.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class EpisodicSummary:
    """A bounded, provenance-carrying compression of canonical history."""

    summary_id: str
    playthrough_id: str
    branch_id: str
    source_revision: int
    start_world_time: int
    end_world_time: int
    turn_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    salient_source_ids: tuple[str, ...]
    text: str
    summary_version: str = "episodic-summary"
    derived: bool = True

    def __post_init__(self) -> None:
        if not self.summary_id.strip() or not self.playthrough_id.strip() or not self.branch_id.strip():
            raise ValueError("Summary identity and scope are required.")
        if self.source_revision < 0 or self.start_world_time < 0 or self.end_world_time < self.start_world_time:
            raise ValueError("Summary revision and time range are invalid.")
        if not self.turn_ids or not self.text.strip():
            raise ValueError("Summary requires source turns and text.")
        object.__setattr__(self, "turn_ids", tuple(dict.fromkeys(self.turn_ids)))
        object.__setattr__(self, "source_ids", tuple(dict.fromkeys(self.source_ids)))
        object.__setattr__(self, "salient_source_ids", tuple(dict.fromkeys(self.salient_source_ids)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "playthrough_id": self.playthrough_id,
            "branch_id": self.branch_id,
            "source_revision": self.source_revision,
            "start_world_time": self.start_world_time,
            "end_world_time": self.end_world_time,
            "turn_ids": list(self.turn_ids),
            "source_ids": list(self.source_ids),
            "salient_source_ids": list(self.salient_source_ids),
            "text": self.text,
            "summary_version": self.summary_version,
            "derived": self.derived,
        }


@dataclass(frozen=True, slots=True)
class BeliefConflict:
    """A perspective-local conflict that does not assert a new canon fact."""

    conflict_id: str
    believer_id: str
    proposition_key: tuple[str, ...]
    belief_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    severity: float
    reason: str

    def __post_init__(self) -> None:
        if not self.conflict_id.strip() or not self.believer_id.strip() or not self.belief_ids:
            raise ValueError("Belief conflict identity is required.")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("Belief conflict severity must be between 0 and 1.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "believer_id": self.believer_id,
            "proposition_key": list(self.proposition_key),
            "belief_ids": list(self.belief_ids),
            "claim_ids": list(self.claim_ids),
            "severity": self.severity,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class HookPriority:
    """Derived ordering signal for an open narrative hook."""

    hook_id: str
    thread_id: str | None
    status: str
    priority: float
    due_in_world_time: int | None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.hook_id.strip() or not 0.0 <= self.priority <= 1.0:
            raise ValueError("Hook priority is invalid.")
        object.__setattr__(self, "reasons", tuple(dict.fromkeys(self.reasons)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "thread_id": self.thread_id,
            "status": self.status,
            "priority": self.priority,
            "due_in_world_time": self.due_in_world_time,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ThreadHealth:
    """Progress/stagnation signal for one narrative thread."""

    thread_id: str
    status: str
    progress: float
    urgency: float
    turns_since_advance: int
    world_time_since_advance: int
    stagnating: bool
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.thread_id.strip() or min(self.turns_since_advance, self.world_time_since_advance) < 0:
            raise ValueError("Thread health identity or age is invalid.")
        if not all(0.0 <= value <= 1.0 for value in (self.progress, self.urgency)):
            raise ValueError("Thread progress and urgency must be between 0 and 1.")
        object.__setattr__(self, "reasons", tuple(dict.fromkeys(self.reasons)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "status": self.status,
            "progress": self.progress,
            "urgency": self.urgency,
            "turns_since_advance": self.turns_since_advance,
            "world_time_since_advance": self.world_time_since_advance,
            "stagnating": self.stagnating,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class RelationshipTrend:
    """Derived trend over immutable relationship change records."""

    source_id: str
    target_id: str
    dimension: str
    direction: str
    slope: float
    latest_value: float
    volatility: float
    sample_count: int
    turn_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.target_id.strip() or not self.dimension.strip():
            raise ValueError("Relationship trend identity is required.")
        if self.sample_count <= 0:
            raise ValueError("Relationship trend requires at least one sample.")
        if not all(isfinite(value) for value in (self.slope, self.latest_value, self.volatility)) or self.volatility < 0:
            raise ValueError("Relationship trend values must be finite.")
        object.__setattr__(self, "turn_ids", tuple(dict.fromkeys(self.turn_ids)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "dimension": self.dimension,
            "direction": self.direction,
            "slope": self.slope,
            "latest_value": self.latest_value,
            "volatility": self.volatility,
            "sample_count": self.sample_count,
            "turn_ids": list(self.turn_ids),
        }


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationDashboard:
    """Aggregate retrieval quality metrics from safe retrieval traces."""

    trace_count: int
    evaluated_query_count: int
    hit_rate_at_k: float
    recall_at_k: float | None
    mean_selected_count: float
    hard_filter_rate: float
    by_phase: dict[str, dict[str, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if min(self.trace_count, self.evaluated_query_count) < 0:
            raise ValueError("Retrieval dashboard counts cannot be negative.")
        for value in (self.hit_rate_at_k, self.hard_filter_rate):
            if not 0.0 <= value <= 1.0:
                raise ValueError("Retrieval dashboard rates must be between 0 and 1.")
        if self.recall_at_k is not None and not 0.0 <= self.recall_at_k <= 1.0:
            raise ValueError("Retrieval recall must be between 0 and 1.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "trace_count": self.trace_count,
            "evaluated_query_count": self.evaluated_query_count,
            "hit_rate_at_k": self.hit_rate_at_k,
            "recall_at_k": self.recall_at_k,
            "mean_selected_count": self.mean_selected_count,
            "hard_filter_rate": self.hard_filter_rate,
            "by_phase": {key: dict(value) for key, value in self.by_phase.items()},
        }


@dataclass(frozen=True, slots=True)
class EmbeddingRebuildReport:
    """Result of rebuilding only derived vectors."""

    playthrough_id: str
    branch_id: str
    candidate_count: int
    indexed_count: int
    model: str | None
    embedding_version: str
    failed_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if min(self.candidate_count, self.indexed_count) < 0 or self.indexed_count > self.candidate_count:
            raise ValueError("Embedding rebuild counts are invalid.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "playthrough_id": self.playthrough_id,
            "branch_id": self.branch_id,
            "candidate_count": self.candidate_count,
            "indexed_count": self.indexed_count,
            "model": self.model,
            "embedding_version": self.embedding_version,
            "failed_source_ids": list(self.failed_source_ids),
        }


__all__ = [
    "BeliefConflict",
    "EmbeddingRebuildReport",
    "EpisodicSummary",
    "HookPriority",
    "RelationshipTrend",
    "RetrievalEvaluationDashboard",
    "ThreadHealth",
]
