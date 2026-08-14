"""Directed relationship vectors and dimension-specific policies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from .errors import DomainValidationError
from .values import Provenance, clamp


class RelationshipDimension(StrEnum):
    AFFECTION = "affection"
    ATTRACTION = "attraction"
    TRUST = "trust"
    RESPECT = "respect"
    COMFORT = "comfort"
    FEAR = "fear"
    RESENTMENT = "resentment"
    FAMILIARITY = "familiarity"


RELATIONSHIP_BOUNDS: dict[str, tuple[float, float]] = {
    RelationshipDimension.AFFECTION: (-1.0, 1.0),
    RelationshipDimension.ATTRACTION: (0.0, 1.0),
    RelationshipDimension.TRUST: (0.0, 1.0),
    RelationshipDimension.RESPECT: (-1.0, 1.0),
    RelationshipDimension.COMFORT: (0.0, 1.0),
    RelationshipDimension.FEAR: (0.0, 1.0),
    RelationshipDimension.RESENTMENT: (0.0, 1.0),
    RelationshipDimension.FAMILIARITY: (0.0, 1.0),
}


@dataclass(frozen=True, slots=True)
class RelationshipPolicy:
    """Independent validation policy for one relationship dimension."""

    dimension: str
    lower: float
    upper: float

    def __post_init__(self) -> None:
        expected = RELATIONSHIP_BOUNDS.get(self.dimension)
        if expected is None:
            raise DomainValidationError("unknown_relationship_dimension", f"Unknown relationship dimension: {self.dimension}.")
        if self.lower != expected[0] or self.upper != expected[1]:
            raise DomainValidationError("invalid_relationship_policy", f"Policy bounds do not match {self.dimension}.")

    def apply(self, current: float, proposed_delta: float) -> tuple[float, float]:
        if not isinstance(proposed_delta, (int, float)) or isinstance(proposed_delta, bool):
            raise DomainValidationError("invalid_relationship_delta", "Relationship delta must be numeric.")
        before = clamp(float(current), self.lower, self.upper)
        after = clamp(before + float(proposed_delta), self.lower, self.upper)
        return after - before, after


DEFAULT_RELATIONSHIP_POLICIES = {
    dimension: RelationshipPolicy(dimension, *bounds) for dimension, bounds in RELATIONSHIP_BOUNDS.items()
}


@dataclass(frozen=True, slots=True)
class RelationshipVector:
    """All directed dimensions for one source -> target edge."""

    values: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = {dimension: 0.0 for dimension in RELATIONSHIP_BOUNDS}
        for dimension, value in self.values.items():
            policy = DEFAULT_RELATIONSHIP_POLICIES.get(str(dimension))
            if policy is None:
                raise DomainValidationError("unknown_relationship_dimension", f"Unknown relationship dimension: {dimension}.")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise DomainValidationError("invalid_relationship_value", f"Relationship value for {dimension} must be numeric.")
            normalized[str(dimension)] = clamp(float(value), policy.lower, policy.upper)
        object.__setattr__(self, "values", normalized)

    @classmethod
    def zero(cls) -> RelationshipVector:
        return cls()

    @classmethod
    def from_mapping(cls, values: Mapping[str, float]) -> RelationshipVector:
        return cls(values)

    def value(self, dimension: str | RelationshipDimension) -> float:
        key = str(dimension)
        if key not in RELATIONSHIP_BOUNDS:
            raise DomainValidationError("unknown_relationship_dimension", f"Unknown relationship dimension: {key}.")
        return self.values[key]

    def with_value(self, dimension: str | RelationshipDimension, value: float) -> RelationshipVector:
        key = str(dimension)
        policy = DEFAULT_RELATIONSHIP_POLICIES.get(key)
        if policy is None:
            raise DomainValidationError("unknown_relationship_dimension", f"Unknown relationship dimension: {key}.")
        if key == RelationshipDimension.FAMILIARITY:
            raise DomainValidationError("familiarity_is_engine_derived", "Familiarity cannot be directly mutated.")
        return RelationshipVector({**self.values, key: policy.apply(0.0, value)[1]})

    def apply_delta(
        self, dimension: str | RelationshipDimension, proposed_delta: float
    ) -> tuple[RelationshipVector, float, float]:
        key = str(dimension)
        policy = DEFAULT_RELATIONSHIP_POLICIES.get(key)
        if policy is None:
            raise DomainValidationError("unknown_relationship_dimension", f"Unknown relationship dimension: {key}.")
        if key == RelationshipDimension.FAMILIARITY:
            raise DomainValidationError("familiarity_is_engine_derived", "Familiarity is derived from world history.")
        validated_delta, after = policy.apply(self.value(key), proposed_delta)
        return RelationshipVector({**self.values, key: after}), validated_delta, after

    def label(self) -> str:
        """A deliberately coarse projection; the vector remains authoritative."""
        affection = self.value(RelationshipDimension.AFFECTION)
        trust = self.value(RelationshipDimension.TRUST)
        respect = self.value(RelationshipDimension.RESPECT)
        familiarity = self.value(RelationshipDimension.FAMILIARITY)
        if affection >= 0.65 and trust >= 0.6 and familiarity >= 0.45:
            return "close"
        if affection >= 0.25 and familiarity >= 0.2:
            return "fond"
        if respect >= 0.45 and trust >= 0.35:
            return "ally"
        if respect <= -0.45 or self.value(RelationshipDimension.RESENTMENT) >= 0.65:
            return "adversarial"
        if familiarity >= 0.15:
            return "acquainted"
        return "unknown"


@dataclass(frozen=True, slots=True)
class RelationshipChange:
    """Auditable before/proposed/validated/after relationship mutation."""

    source_id: str
    target_id: str
    dimension: str
    before: float
    proposed_delta: float
    validated_delta: float
    after: float
    cause_event_id: str
    reason: str
    provenance: Provenance


def derive_familiarity(
    *,
    shared_scene_count: int = 0,
    meaningful_event_count: int = 0,
    elapsed_minutes: int = 0,
) -> float:
    """Derive familiarity monotonically from history, never from a direct delta."""
    if min(shared_scene_count, meaningful_event_count, elapsed_minutes) < 0:
        raise DomainValidationError("invalid_familiarity_signal", "Familiarity signals cannot be negative.")
    scene_signal = 1.0 - 1.0 / (1.0 + shared_scene_count / 3.0)
    event_signal = 1.0 - 1.0 / (1.0 + meaningful_event_count / 2.0)
    time_signal = 1.0 - 1.0 / (1.0 + elapsed_minutes / (60.0 * 24.0 * 30.0))
    return clamp(0.5 * scene_signal + 0.35 * event_signal + 0.15 * time_signal, 0.0, 1.0)


__all__ = [
    "DEFAULT_RELATIONSHIP_POLICIES",
    "RELATIONSHIP_BOUNDS",
    "RelationshipChange",
    "RelationshipDimension",
    "RelationshipPolicy",
    "RelationshipVector",
    "derive_familiarity",
]
