"""Secret-safe telemetry contracts for optional runtime profiling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    """Explicit opt-in policy for local profiling data."""

    enabled: bool = False
    output_path: str | None = None
    prompt_cost_per_1k_tokens: float = 0.0
    completion_cost_per_1k_tokens: float = 0.0
    max_samples: int = 10_000

    def __post_init__(self) -> None:
        if self.prompt_cost_per_1k_tokens < 0 or self.completion_cost_per_1k_tokens < 0:
            raise ValueError("Telemetry token costs cannot be negative.")
        if self.max_samples < 1:
            raise ValueError("Telemetry max_samples must be positive.")


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """One bounded, prompt-free provider timing/cost sample."""

    recorded_at: datetime
    run_id: str
    logical_role: str
    physical_call_id: str
    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float = 0.0
    retry_count: int = 0
    fallback_from: str | None = None

    def __post_init__(self) -> None:
        if self.recorded_at.tzinfo is None:
            raise ValueError("Telemetry timestamps must be timezone-aware.")
        if self.latency_ms < 0 or self.estimated_cost_usd < 0 or self.retry_count < 0:
            raise ValueError("Telemetry measurements cannot be negative.")
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative.")

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-safe metadata; raw prompts and provider output are absent."""
        return {
            "schema_version": "telemetry-event-1",
            "recorded_at": self.recorded_at.astimezone(UTC).isoformat(),
            "run_id": self.run_id,
            "logical_role": self.logical_role,
            "physical_call_id": self.physical_call_id,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "retry_count": self.retry_count,
            "fallback_from": self.fallback_from,
        }

    def as_json(self) -> str:
        """Serialize one event for the append-only local JSONL sink."""
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True, slots=True)
class TelemetrySummary:
    """Aggregate latency, token and estimated-cost measurements."""

    sample_count: int
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


__all__ = ["TelemetryConfig", "TelemetryEvent", "TelemetrySummary"]
