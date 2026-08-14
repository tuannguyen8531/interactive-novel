"""Bounded psychological state used by the deterministic simulator."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from .errors import DomainValidationError
from .values import clamp


def _bounded(value: float, field_name: str, lower: float = 0.0, upper: float = 1.0) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not lower <= value <= upper:
        raise DomainValidationError("psychology_value_out_of_range", f"{field_name} must be between {lower} and {upper}.")
    return float(value)


@dataclass(frozen=True, slots=True)
class PsychologicalState:
    """Short-lived affect and motivation; profile data remains elsewhere."""

    valence: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0
    stress: float = 0.0
    fatigue: float = 0.0
    needs: Mapping[str, float] = field(default_factory=dict)
    active_goals: tuple[str, ...] = ()
    appraisals: Mapping[str, float] = field(default_factory=dict)
    suppressed_emotions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _bounded(self.valence, "valence", -1.0, 1.0)
        for name in ("arousal", "dominance", "stress", "fatigue"):
            _bounded(getattr(self, name), name)
        object.__setattr__(self, "needs", {key: _bounded(value, f"needs.{key}") for key, value in self.needs.items()})
        object.__setattr__(self, "active_goals", tuple(self.active_goals))
        object.__setattr__(
            self,
            "appraisals",
            {key: _bounded(value, f"appraisals.{key}", -1.0, 1.0) for key, value in self.appraisals.items()},
        )
        object.__setattr__(self, "suppressed_emotions", tuple(self.suppressed_emotions))

    @property
    def control(self) -> float:
        """Alias for the domain-model term "dominance/control"."""
        return self.dominance

    def apply_deltas(self, deltas: Mapping[str, float]) -> PsychologicalState:
        """Apply typed numeric deltas while preserving every range invariant."""
        allowed = {"valence", "arousal", "dominance", "stress", "fatigue"}
        unknown = set(deltas) - allowed
        if unknown:
            raise DomainValidationError("unknown_psychology_delta", f"Unknown psychology fields: {sorted(unknown)}.")
        updates: dict[str, float] = {}
        for name in allowed:
            delta = deltas.get(name, 0.0)
            if not isinstance(delta, (int, float)) or isinstance(delta, bool):
                raise DomainValidationError("invalid_psychology_delta", f"Delta for {name} must be numeric.")
            lower = -1.0 if name == "valence" else 0.0
            updates[name] = clamp(float(getattr(self, name)) + float(delta), lower, 1.0)
        return replace(self, **updates)


__all__ = ["PsychologicalState"]
