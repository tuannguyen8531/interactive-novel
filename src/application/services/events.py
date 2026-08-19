"""In-process job event bus with bounded replay for SSE clients."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from typing import Any

from src.application.contracts.jobs import JobEvent


class InMemoryJobEventBroker:
    """Route safe graph/job events to subscribers and retain recent replay."""

    def __init__(self, *, history_size: int = 256, queue_size: int = 128) -> None:
        if history_size <= 0 or queue_size <= 0:
            raise ValueError("Event broker sizes must be positive.")
        self._history_size = history_size
        self._queue_size = queue_size
        self._history: dict[str, deque[JobEvent]] = defaultdict(lambda: deque(maxlen=self._history_size))
        self._next_sequence: dict[str, int] = defaultdict(int)
        self._run_to_job: dict[str, str] = {}
        self._subscribers: dict[str, set[asyncio.Queue[JobEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def register(self, *, job_id: str, turn_run_id: str) -> None:
        async with self._lock:
            self._run_to_job[turn_run_id] = job_id
            self._history.setdefault(job_id, deque(maxlen=self._history_size))

    async def publish(self, event: Any) -> JobEvent | None:
        """Accept a graph ``NodeEvent`` without importing graph into application."""
        turn_run_id = str(getattr(event, "turn_run_id", ""))
        job_id = self._run_to_job.get(turn_run_id)
        if job_id is None:
            return None
        # The graph's enqueue node emits a bookkeeping ``completed`` event as
        # soon as its node returns. The coordinator emits the public terminal
        # event only after it has persisted the job outcome.
        if str(getattr(event, "event_type", "")) == "completed":
            return None
        payload = getattr(event, "payload", {})
        if not isinstance(payload, Mapping):
            payload = {"value": payload}
        return await self.publish_job_event(
            job_id=job_id,
            turn_run_id=turn_run_id,
            event_type=str(getattr(event, "event_type", "progress")),
            phase=str(getattr(event, "node", "turn")),
            payload=dict(payload),
        )

    async def publish_job_event(
        self,
        *,
        job_id: str,
        turn_run_id: str,
        event_type: str,
        phase: str,
        payload: Mapping[str, Any] | None = None,
        terminal: bool = False,
    ) -> JobEvent:
        async with self._lock:
            self._next_sequence[job_id] += 1
            event = JobEvent(
                id=str(self._next_sequence[job_id]),
                job_id=job_id,
                turn_run_id=turn_run_id,
                event_type=event_type,
                phase=phase,
                payload=dict(payload or {}),
                terminal=terminal,
            )
            self._history[job_id].append(event)
            subscribers = tuple(self._subscribers.get(job_id, ()))
        for queue in subscribers:
            with suppress(asyncio.QueueFull):
                queue.put_nowait(event)
        return event

    async def history(self, job_id: str, *, after: str | None = None) -> tuple[JobEvent, ...]:
        after_sequence = _sequence_from_id(after)
        async with self._lock:
            return tuple(event for event in self._history.get(job_id, ()) if int(event.id) > after_sequence)

    async def subscribe(self, job_id: str, *, last_event_id: str | None = None) -> AsyncIterator[JobEvent]:
        """Replay buffered events, then wait for live events until terminal."""
        queue: asyncio.Queue[JobEvent] = asyncio.Queue(maxsize=self._queue_size)
        after_sequence = _sequence_from_id(last_event_id)
        async with self._lock:
            replay = tuple(event for event in self._history.get(job_id, ()) if int(event.id) > after_sequence)
            self._subscribers[job_id].add(queue)
        try:
            for event in replay:
                yield event
                if event.terminal:
                    return
            while True:
                event = await queue.get()
                yield event
                if event.terminal:
                    return
        finally:
            async with self._lock:
                self._subscribers[job_id].discard(queue)


def _sequence_from_id(value: str | None) -> int:
    if value is None or not value.strip():
        return 0
    try:
        return max(0, int(value.strip()))
    except ValueError:
        return 0


__all__ = ["InMemoryJobEventBroker"]
