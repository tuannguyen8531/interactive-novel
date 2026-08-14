"""Immutable events and perspective-specific knowledge records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import DomainValidationError
from .values import Provenance


def _check_time(value: int, field_name: str = "world_time") -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainValidationError("invalid_world_time", f"{field_name} must be a non-negative integer.")


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    event_type: str
    world_time: int
    branch_scope: str
    location_id: str | None = None
    actor_ids: tuple[str, ...] = ()
    target_ids: tuple[str, ...] = ()
    witness_ids: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)
    salience: float = 0.5
    emotional_intensity: float = 0.0
    cause_event_ids: tuple[str, ...] = ()
    turn_id: str | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.event_type.strip() or not self.branch_scope.strip():
            raise DomainValidationError("invalid_event", "Event identity, type and branch scope are required.")
        _check_time(self.world_time)
        for field_name in ("salience", "emotional_intensity"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
                raise DomainValidationError("event_value_out_of_range", f"{field_name} must be between 0 and 1.")
        object.__setattr__(self, "actor_ids", tuple(self.actor_ids))
        object.__setattr__(self, "target_ids", tuple(self.target_ids))
        object.__setattr__(self, "witness_ids", tuple(self.witness_ids))
        object.__setattr__(self, "cause_event_ids", tuple(self.cause_event_ids))
        object.__setattr__(self, "payload", dict(self.payload))

    @property
    def actors(self) -> tuple[str, ...]:
        return self.actor_ids

    @property
    def targets(self) -> tuple[str, ...]:
        return self.target_ids

    @property
    def witnesses(self) -> tuple[str, ...]:
        return self.witness_ids


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    owner_id: str
    source_event_id: str
    claim_id: str
    branch_scope: str
    world_time: int
    method: str = "observed"
    confidence: float = 1.0
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not all(
            value.strip() for value in (self.evidence_id, self.owner_id, self.source_event_id, self.claim_id, self.branch_scope)
        ):
            raise DomainValidationError("invalid_evidence", "Evidence identity and scope are required.")
        _check_time(self.world_time)
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainValidationError("evidence_value_out_of_range", "Evidence confidence must be between 0 and 1.")


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    observer_id: str
    observed_claim_id: str
    source_event_id: str
    method: str
    branch_scope: str
    world_time: int
    confidence: float = 1.0
    distortion: float = 0.0
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.observation_id,
                self.observer_id,
                self.observed_claim_id,
                self.source_event_id,
                self.method,
                self.branch_scope,
            )
        ):
            raise DomainValidationError("invalid_observation", "Observation identity, method and scope are required.")
        _check_time(self.world_time)
        if not 0.0 <= self.confidence <= 1.0 or not 0.0 <= self.distortion <= 1.0:
            raise DomainValidationError(
                "observation_value_out_of_range", "Observation confidence and distortion must be between 0 and 1."
            )


@dataclass(frozen=True, slots=True)
class Belief:
    belief_id: str
    believer_id: str
    claim_id: str
    stance: str = "uncertain"
    confidence: float = 0.5
    evidence_ids: tuple[str, ...] = ()
    counter_evidence_ids: tuple[str, ...] = ()
    branch_scope: str = "public"
    world_time: int = 0
    source_reliability: float = 0.5
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.belief_id, self.believer_id, self.claim_id, self.branch_scope)):
            raise DomainValidationError("invalid_belief", "Belief identity and scope are required.")
        _check_time(self.world_time)
        for name in ("confidence", "source_reliability"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise DomainValidationError("belief_value_out_of_range", f"{name} must be between 0 and 1.")
        if self.stance not in {"supports", "rejects", "uncertain"}:
            raise DomainValidationError("invalid_belief_stance", "Belief stance must be supports, rejects or uncertain.")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        object.__setattr__(self, "counter_evidence_ids", tuple(self.counter_evidence_ids))


__all__ = ["Belief", "Event", "Evidence", "Observation"]
