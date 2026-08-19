"""Safe node progress events for the turn graph."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class NodeEvent:
    """A secret-safe event; raw prompts and provider output are never included."""

    event_type: str
    node: str
    turn_run_id: str
    sequence: int
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "node": self.node,
            "turn_run_id": self.turn_run_id,
            "sequence": self.sequence,
            "payload": dict(self.payload),
            "created_at": self.created_at.isoformat(),
        }


class EventSink(Protocol):
    """Optional streaming boundary owned by an outer application/API layer."""

    async def publish(self, event: NodeEvent) -> None: ...


class InMemoryEventSink:
    """Small deterministic sink useful for headless tests and local inspection."""

    def __init__(self) -> None:
        self.events: list[NodeEvent] = []

    async def publish(self, event: NodeEvent) -> None:
        self.events.append(event)


AsyncEventCallback = Callable[[NodeEvent], Awaitable[None]]


async def publish_event(sink: EventSink | AsyncEventCallback | None, event: NodeEvent) -> None:
    if sink is None:
        return
    if hasattr(sink, "publish"):
        await sink.publish(event)  # type: ignore[union-attr]
        return
    await sink(event)  # type: ignore[operator]


__all__ = ["AsyncEventCallback", "EventSink", "InMemoryEventSink", "NodeEvent", "publish_event"]
