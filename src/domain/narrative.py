"""Narrative thread and hook lifecycle entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from .errors import DomainValidationError
from .values import TimeRange, clamp


class ThreadStatus(StrEnum):
    SEEDED = "seeded"
    ACTIVE = "active"
    ESCALATING = "escalating"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


THREAD_TRANSITIONS: dict[ThreadStatus, set[ThreadStatus]] = {
    ThreadStatus.SEEDED: {ThreadStatus.ACTIVE, ThreadStatus.ABANDONED},
    ThreadStatus.ACTIVE: {ThreadStatus.ESCALATING, ThreadStatus.RESOLVED, ThreadStatus.ABANDONED},
    ThreadStatus.ESCALATING: {ThreadStatus.ACTIVE, ThreadStatus.RESOLVED, ThreadStatus.ABANDONED},
    ThreadStatus.RESOLVED: set(),
    ThreadStatus.ABANDONED: set(),
}


class HookStatus(StrEnum):
    OPEN = "open"
    PAID = "paid"
    EXPIRED = "expired"
    ABANDONED = "abandoned"


HOOK_TRANSITIONS: dict[HookStatus, set[HookStatus]] = {
    HookStatus.OPEN: {HookStatus.PAID, HookStatus.EXPIRED, HookStatus.ABANDONED},
    HookStatus.PAID: set(),
    HookStatus.EXPIRED: set(),
    HookStatus.ABANDONED: set(),
}


@dataclass(frozen=True, slots=True)
class NarrativeThread:
    thread_id: str
    premise: str
    branch_scope: str
    participant_ids: tuple[str, ...] = ()
    status: ThreadStatus = ThreadStatus.SEEDED
    stakes: str = ""
    progress: float = 0.0
    urgency: float = 0.0
    last_advanced_world_time: int | None = None
    resolution_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.thread_id.strip() or not self.premise.strip() or not self.branch_scope.strip():
            raise DomainValidationError("invalid_narrative_thread", "Thread identity, premise and scope are required.")
        for name in ("progress", "urgency"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise DomainValidationError("narrative_value_out_of_range", f"{name} must be between 0 and 1.")
        if self.last_advanced_world_time is not None and self.last_advanced_world_time < 0:
            raise DomainValidationError("invalid_world_time", "Thread advancement time cannot be negative.")
        object.__setattr__(self, "status", ThreadStatus(self.status))
        object.__setattr__(self, "participant_ids", tuple(self.participant_ids))
        object.__setattr__(self, "resolution_conditions", tuple(self.resolution_conditions))

    def transition(
        self, status: ThreadStatus | str, *, progress_delta: float = 0.0, world_time: int | None = None
    ) -> NarrativeThread:
        next_status = ThreadStatus(status)
        if next_status not in THREAD_TRANSITIONS[self.status]:
            raise DomainValidationError(
                "invalid_thread_transition", f"Thread cannot transition from {self.status} to {next_status}."
            )
        if world_time is not None and world_time < 0:
            raise DomainValidationError("invalid_world_time", "Thread transition time cannot be negative.")
        next_progress = clamp(self.progress + progress_delta, 0.0, 1.0)
        return replace(self, status=next_status, progress=next_progress, last_advanced_world_time=world_time)


@dataclass(frozen=True, slots=True)
class NarrativeHook:
    hook_id: str
    setup: str
    branch_scope: str
    payoff_window: TimeRange
    related_thread_id: str | None = None
    related_event_id: str | None = None
    visibility: str = "public"
    status: HookStatus = HookStatus.OPEN

    def __post_init__(self) -> None:
        if not self.hook_id.strip() or not self.setup.strip() or not self.branch_scope.strip():
            raise DomainValidationError("invalid_narrative_hook", "Hook identity, setup and scope are required.")
        object.__setattr__(self, "status", HookStatus(self.status))

    def transition(self, status: HookStatus | str) -> NarrativeHook:
        next_status = HookStatus(status)
        if next_status not in HOOK_TRANSITIONS[self.status]:
            raise DomainValidationError("invalid_hook_transition", f"Hook cannot transition from {self.status} to {next_status}.")
        return replace(self, status=next_status)


__all__ = [
    "HOOK_TRANSITIONS",
    "THREAD_TRANSITIONS",
    "HookStatus",
    "NarrativeHook",
    "NarrativeThread",
    "ThreadStatus",
]
