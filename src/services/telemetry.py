"""Opt-in, bounded, secret-safe runtime telemetry."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from src.application.contracts.ai import LLMRunTrace
from src.application.contracts.telemetry import TelemetryConfig, TelemetryEvent, TelemetrySummary


class TelemetrySink(Protocol):
    """Storage adapter for already-redacted telemetry events."""

    def append(self, event: TelemetryEvent) -> None:
        """Persist one event."""
        ...


class InMemoryTelemetrySink:
    """Small test and local-inspection sink."""

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    @property
    def events(self) -> tuple[TelemetryEvent, ...]:
        return tuple(self._events)

    def append(self, event: TelemetryEvent) -> None:
        self._events.append(event)


class JsonlTelemetrySink:
    """Append only secret-free JSONL records under the configured runtime path."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()

    def append(self, event: TelemetryEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(f"{event.as_json()}\n")


class TelemetryRecorder:
    """Record LLM traces only when the user explicitly enables telemetry."""

    def __init__(self, config: TelemetryConfig, *, sink: TelemetrySink | None = None) -> None:
        self.config = config
        self._sink = sink
        self._events: deque[TelemetryEvent] = deque(maxlen=config.max_samples)

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @property
    def events(self) -> tuple[TelemetryEvent, ...]:
        return tuple(self._events)

    def record(self, trace: LLMRunTrace) -> None:
        if not self.config.enabled:
            return
        usage = trace.token_usage
        prompt_tokens = usage.prompt_tokens if usage is not None else None
        completion_tokens = usage.completion_tokens if usage is not None else None
        total_tokens = usage.total_tokens if usage is not None else None
        cost = _estimated_cost(
            prompt_tokens,
            completion_tokens,
            prompt_rate=self.config.prompt_cost_per_1k_tokens,
            completion_rate=self.config.completion_cost_per_1k_tokens,
        )
        event = TelemetryEvent(
            recorded_at=datetime.now(UTC),
            run_id=trace.run_id,
            logical_role=trace.logical_role.value,
            physical_call_id=trace.physical_call_id,
            provider=trace.provider,
            model=trace.model,
            latency_ms=trace.latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            retry_count=trace.retry_count,
            fallback_from=trace.fallback_from,
        )
        self._events.append(event)
        if self._sink is not None:
            try:
                self._sink.append(event)
            except OSError:
                # Telemetry is never authoritative and must not fail a turn.
                return

    def summary(self, events: Iterable[TelemetryEvent] | None = None) -> TelemetrySummary:
        samples = tuple(events if events is not None else self._events)
        latencies = sorted(event.latency_ms for event in samples)
        return TelemetrySummary(
            sample_count=len(samples),
            p50_latency_ms=_percentile(latencies, 0.50),
            p95_latency_ms=_percentile(latencies, 0.95),
            prompt_tokens=sum(event.prompt_tokens or 0 for event in samples),
            completion_tokens=sum(event.completion_tokens or 0 for event in samples),
            total_tokens=sum(event.total_tokens or 0 for event in samples),
            estimated_cost_usd=round(sum(event.estimated_cost_usd for event in samples), 10),
        )


def build_telemetry_recorder(
    config: TelemetryConfig,
    *,
    output_path: Path | None = None,
) -> TelemetryRecorder:
    """Build the configured sink without creating files when telemetry is off."""
    sink = JsonlTelemetrySink(output_path) if config.enabled and output_path is not None else None
    return TelemetryRecorder(config, sink=sink)


def _estimated_cost(
    prompt_tokens: int | None,
    completion_tokens: int | None,
    *,
    prompt_rate: float,
    completion_rate: float,
) -> float:
    return round(
        ((prompt_tokens or 0) / 1_000 * prompt_rate) + ((completion_tokens or 0) / 1_000 * completion_rate),
        10,
    )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, math.ceil(len(values) * percentile) - 1))
    return values[index]


__all__ = [
    "InMemoryTelemetrySink",
    "JsonlTelemetrySink",
    "TelemetryRecorder",
    "TelemetrySink",
    "build_telemetry_recorder",
]
