"""Reproducible latency/token/cost reporting from secret-safe telemetry."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class QualityBenchmarkReport:
    sample_count: int
    turn_count: int
    p95_estimated_turn_latency_ms: float | None
    average_cost_per_turn_usd: float | None
    total_tokens: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "turn_count": self.turn_count,
            "p95_estimated_turn_latency_ms": self.p95_estimated_turn_latency_ms,
            "average_cost_per_turn_usd": self.average_cost_per_turn_usd,
            "total_tokens": self.total_tokens,
        }


def benchmark_telemetry(path: Path) -> QualityBenchmarkReport:
    """Aggregate provider-real samples by run without reading prompts or outputs."""
    if not path.is_file():
        return QualityBenchmarkReport(0, 0, None, None, 0)
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict) and isinstance(value.get("run_id"), str):
            events.append(value)
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_run[str(event["run_id"])].append(event)
    latencies = sorted(sum(float(item.get("latency_ms") or 0.0) for item in items) for items in by_run.values())
    costs = [sum(float(item.get("estimated_cost_usd") or 0.0) for item in items) for items in by_run.values()]
    p95 = None if not latencies else latencies[min(len(latencies) - 1, math.ceil(len(latencies) * 0.95) - 1)]
    average_cost = None if not costs else sum(costs) / len(costs)
    return QualityBenchmarkReport(
        sample_count=len(events),
        turn_count=len(by_run),
        p95_estimated_turn_latency_ms=p95,
        average_cost_per_turn_usd=average_cost,
        total_tokens=sum(int(item.get("total_tokens") or 0) for item in events),
    )


__all__ = ["QualityBenchmarkReport", "benchmark_telemetry"]
