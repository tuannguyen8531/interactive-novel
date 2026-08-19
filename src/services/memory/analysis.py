"""Pure, rebuildable memory and narrative analysis.

Every function in this module consumes canonical records and returns derived
records.  It never mutates a :class:`GameState`, creates a CanonFact, or
changes a relationship/thread.  That boundary is what makes a failed or
stale derived job safe to ignore while gameplay continues from canon.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256

from src.application.contracts.memory import (
    BeliefConflict,
    EpisodicSummary,
    HookPriority,
    RelationshipTrend,
    RetrievalEvaluationDashboard,
    ThreadHealth,
)
from src.application.contracts.persistence import (
    BeliefRecord,
    KnowledgeClaimRecord,
    NarrativeHookRecord,
    NarrativeThreadRecord,
    RelationshipChangeRecord,
    TurnRecord,
)
from src.application.contracts.retrieval import MemoryCandidate, RetrievalTrace


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _candidate_line(candidate: MemoryCandidate) -> str:
    payload = candidate.payload
    detail = next(
        (str(payload[key]).strip() for key in ("text", "summary", "description", "narrative") if payload.get(key)),
        candidate.text,
    )
    return f"{candidate.kind}: {detail}"


class MemoryConsolidator:
    """Build bounded episodic summaries while retaining canonical provenance."""

    def __init__(self, *, window_turns: int = 10, max_memory_lines: int = 24) -> None:
        if window_turns <= 0 or max_memory_lines <= 0:
            raise ValueError("Summary window and memory line limits must be positive.")
        self.window_turns = window_turns
        self.max_memory_lines = max_memory_lines

    def consolidate(
        self,
        *,
        playthrough_id: str,
        branch_id: str,
        source_revision: int,
        turns: Sequence[TurnRecord],
        candidates: Sequence[MemoryCandidate] = (),
    ) -> tuple[EpisodicSummary, ...]:
        ordered_turns = sorted(turns, key=lambda item: (item.base_revision + 1, item.world_time_end, item.id))
        summaries: list[EpisodicSummary] = []
        for offset in range(0, len(ordered_turns), self.window_turns):
            window = tuple(ordered_turns[offset : offset + self.window_turns])
            if not window:
                continue
            start_time = min(item.world_time_start for item in window)
            end_time = max(item.world_time_end for item in window)
            window_candidates = [item for item in candidates if start_time <= item.world_time <= max(end_time, start_time)]
            window_candidates.sort(
                key=lambda item: (item.salience + item.emotional_intensity, item.world_time, item.source_id),
                reverse=True,
            )
            selected = window_candidates[: self.max_memory_lines]
            source_ids = tuple(item.source_id for item in window_candidates)
            salient_ids = tuple(item.source_id for item in selected if item.salience >= 0.65)
            lines = [
                f"Episode turns {window[0].base_revision + 1}-{window[-1].base_revision + 1} "
                f"(world time {start_time}-{end_time})."
            ]
            for turn in window:
                if turn.final_narrative:
                    narrative = " ".join(turn.final_narrative.split())
                    lines.append(f"Turn {turn.base_revision + 1}: {narrative[:360]}")
            lines.extend(_candidate_line(item) for item in selected)
            summary_id = f"summary:{branch_id}:{source_revision}:{offset // self.window_turns}"
            summaries.append(
                EpisodicSummary(
                    summary_id=summary_id,
                    playthrough_id=playthrough_id,
                    branch_id=branch_id,
                    source_revision=source_revision,
                    start_world_time=start_time,
                    end_world_time=end_time,
                    turn_ids=tuple(item.id for item in window),
                    source_ids=source_ids,
                    salient_source_ids=salient_ids,
                    text="\n".join(lines),
                )
            )
        return tuple(summaries)


class BeliefConflictDetector:
    """Detect incompatible perspective beliefs without changing either belief."""

    def detect(
        self,
        beliefs: Sequence[BeliefRecord],
        claims: Sequence[KnowledgeClaimRecord],
    ) -> tuple[BeliefConflict, ...]:
        claims_by_id = {claim.claim_id: claim for claim in claims}
        grouped: dict[tuple[str, tuple[str, ...]], dict[int, list[BeliefRecord]]] = defaultdict(lambda: defaultdict(list))
        for belief in beliefs:
            claim = claims_by_id.get(belief.claim_id)
            if claim is None or belief.stance == "uncertain":
                continue
            key = self._proposition_key(claim)
            orientation = 1 if (claim.polarity == "positive") == (belief.stance == "supports") else -1
            grouped[(belief.believer_id, key)][orientation].append(belief)

        conflicts: list[BeliefConflict] = []
        for (believer_id, key), sides in grouped.items():
            positive = sides.get(1, [])
            negative = sides.get(-1, [])
            if not positive or not negative:
                continue
            records = (*positive, *negative)
            claims_for_beliefs = tuple(dict.fromkeys(item.claim_id for item in records))
            severity = _clamp(sum(item.confidence for item in records) / (2 * len(records)))
            fingerprint = sha256("|".join(key).encode("utf-8")).hexdigest()[:16]
            conflicts.append(
                BeliefConflict(
                    conflict_id=f"belief-conflict:{believer_id}:{fingerprint}",
                    believer_id=believer_id,
                    proposition_key=key,
                    belief_ids=tuple(item.belief_id for item in records),
                    claim_ids=claims_for_beliefs,
                    severity=severity,
                    reason="The same character holds supporting and rejecting stances for one proposition.",
                )
            )
        return tuple(sorted(conflicts, key=lambda item: (item.believer_id, item.conflict_id)))

    @staticmethod
    def _proposition_key(claim: KnowledgeClaimRecord) -> tuple[str, ...]:
        typed_value = json.dumps(claim.typed_value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        qualifiers = json.dumps(claim.qualifiers, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return (claim.subject_id, claim.predicate, claim.object_id or "", typed_value, qualifiers)


class HookPrioritizer:
    """Rank open hooks by urgency, payoff pressure and related thread health."""

    def prioritize(
        self,
        hooks: Sequence[NarrativeHookRecord],
        threads: Sequence[NarrativeThreadRecord],
        *,
        current_world_time: int,
    ) -> tuple[HookPriority, ...]:
        thread_by_id = {thread.thread_id: thread for thread in threads}
        results: list[HookPriority] = []
        for hook in hooks:
            if hook.status in {"paid", "expired", "abandoned"}:
                continue
            payload = hook.payload
            thread_id = payload.get("thread_id")
            thread = thread_by_id.get(str(thread_id)) if thread_id else None
            payoff_end = self._int_value(payload, "payoff_window_end", "payoff_end")
            window = payload.get("payoff_window")
            if payoff_end is None and isinstance(window, Mapping):
                payoff_end = self._int_value(window, "end")
            due = None if payoff_end is None else payoff_end - current_world_time
            due_pressure = 0.0 if due is None else (1.0 if due <= 0 else _clamp(1.0 - due / 240.0))
            urgency = thread.urgency if thread is not None else float(payload.get("urgency", 0.5))
            progress = thread.progress if thread is not None else float(payload.get("progress", 0.0))
            priority = _clamp(0.45 * _clamp(urgency) + 0.35 * due_pressure + 0.20 * (1.0 - _clamp(progress)))
            reasons: list[str] = []
            if urgency >= 0.7:
                reasons.append("urgent_thread")
            if due is not None and due <= 0:
                reasons.append("payoff_window_due")
            elif due is not None and due <= 120:
                reasons.append("payoff_window_near")
            if progress < 0.25:
                reasons.append("setup_not_paid")
            results.append(
                HookPriority(
                    hook_id=hook.hook_id,
                    thread_id=None if thread_id is None else str(thread_id),
                    status=hook.status,
                    priority=priority,
                    due_in_world_time=due,
                    reasons=tuple(reasons),
                )
            )
        return tuple(sorted(results, key=lambda item: (-item.priority, item.hook_id)))

    @staticmethod
    def _int_value(payload: Mapping[str, object], *keys: str) -> int | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None


class ThreadStagnationDetector:
    """Flag active threads that stop advancing while retaining their state."""

    def __init__(self, *, turn_threshold: int = 8, world_time_threshold: int = 180) -> None:
        if turn_threshold <= 0 or world_time_threshold <= 0:
            raise ValueError("Thread stagnation thresholds must be positive.")
        self.turn_threshold = turn_threshold
        self.world_time_threshold = world_time_threshold

    def analyze(
        self,
        threads: Sequence[NarrativeThreadRecord],
        *,
        current_turn_index: int,
        current_world_time: int,
        turn_index_by_id: Mapping[str, int] | None = None,
    ) -> tuple[ThreadHealth, ...]:
        indexes = turn_index_by_id or {}
        results: list[ThreadHealth] = []
        for thread in threads:
            payload = thread.payload
            last_turn = payload.get("last_advanced_turn")
            if not isinstance(last_turn, int):
                last_turn = indexes.get(thread.turn_id, current_turn_index)
            last_time = payload.get("last_advanced_world_time", payload.get("world_time", current_world_time))
            if not isinstance(last_time, int):
                last_time = current_world_time
            turns_since = max(0, current_turn_index - last_turn)
            time_since = max(0, current_world_time - last_time)
            is_active = thread.status in {"seeded", "active", "escalating"}
            stagnating = is_active and (turns_since >= self.turn_threshold or time_since >= self.world_time_threshold)
            reasons = []
            if turns_since >= self.turn_threshold:
                reasons.append("turns_without_advance")
            if time_since >= self.world_time_threshold:
                reasons.append("world_time_without_advance")
            if thread.urgency >= 0.7 and stagnating:
                reasons.append("urgent_thread_stagnating")
            results.append(
                ThreadHealth(
                    thread_id=thread.thread_id,
                    status=thread.status,
                    progress=thread.progress,
                    urgency=thread.urgency,
                    turns_since_advance=turns_since,
                    world_time_since_advance=time_since,
                    stagnating=stagnating,
                    reasons=tuple(reasons),
                )
            )
        return tuple(sorted(results, key=lambda item: (-item.urgency, item.thread_id)))


class RelationshipTrendAnalyzer:
    """Compute trends from the immutable relationship change audit trail."""

    def analyze(self, changes: Sequence[RelationshipChangeRecord]) -> tuple[RelationshipTrend, ...]:
        grouped: dict[tuple[str, str, str], list[RelationshipChangeRecord]] = defaultdict(list)
        for change in changes:
            grouped[(change.relationship_id, change.dimension, change.branch_id)].append(change)
        results: list[RelationshipTrend] = []
        for (relationship_id, dimension, _branch_id), records in grouped.items():
            ordered = list(records)
            first = ordered[0]
            source_id, target_id = self._edge(relationship_id, first)
            values = [item.after for item in ordered]
            slope = (values[-1] - values[0]) / max(1, len(values) - 1)
            volatility = sum(abs(right - left) for left, right in zip(values, values[1:], strict=False)) / max(1, len(values) - 1)
            direction = "rising" if slope > 0.02 else "falling" if slope < -0.02 else "stable"
            results.append(
                RelationshipTrend(
                    source_id=source_id,
                    target_id=target_id,
                    dimension=dimension,
                    direction=direction,
                    slope=slope,
                    latest_value=values[-1],
                    volatility=volatility,
                    sample_count=len(values),
                    turn_ids=tuple(item.turn_id for item in ordered),
                )
            )
        return tuple(sorted(results, key=lambda item: (item.source_id, item.target_id, item.dimension)))

    @staticmethod
    def _edge(relationship_id: str, change: RelationshipChangeRecord) -> tuple[str, str]:
        # RelationshipChangeRecord deliberately stores the stable edge ID, not
        # a duplicated edge tuple.  Persistence adapters may include the pair
        # in provenance; a deterministic fallback keeps the report useful.
        provenance = change.provenance
        source_id = str(provenance.get("source_id", ""))
        target_id = str(provenance.get("target_id", ""))
        if source_id and target_id:
            return source_id, target_id
        parts = relationship_id.split(":")
        return (parts[-2], parts[-1]) if len(parts) >= 3 else (relationship_id, "")


class RetrievalEvaluationService:
    """Aggregate trace-only retrieval metrics for scenario evaluation."""

    def evaluate(
        self,
        traces: Sequence[RetrievalTrace],
        *,
        relevant_source_ids: Mapping[str, set[str]] | None = None,
        k: int = 5,
    ) -> RetrievalEvaluationDashboard:
        if k <= 0:
            raise ValueError("Recall cutoff must be positive.")
        expected = relevant_source_ids or {}
        hit_count = 0
        recall_values: list[float] = []
        selected_counts: list[int] = []
        hard_filter_values: list[float] = []
        phase_values: dict[str, list[float]] = defaultdict(list)
        for trace in traces:
            selected = [hit.source_id for hit in trace.hits if hit.selected][:k]
            selected_counts.append(len(selected))
            hit = bool(selected)
            hit_count += int(hit)
            relevant = expected.get(trace.query_id)
            if relevant:
                recall = len(set(selected) & relevant) / len(relevant)
                recall_values.append(recall)
                phase_values[str(trace.phase)].append(recall)
            if trace.candidate_count:
                hard_filter_values.append(trace.hard_filtered_count / trace.candidate_count)
        trace_count = len(traces)
        return RetrievalEvaluationDashboard(
            trace_count=trace_count,
            evaluated_query_count=len(recall_values),
            hit_rate_at_k=hit_count / trace_count if trace_count else 0.0,
            recall_at_k=sum(recall_values) / len(recall_values) if recall_values else None,
            mean_selected_count=sum(selected_counts) / trace_count if trace_count else 0.0,
            hard_filter_rate=sum(hard_filter_values) / len(hard_filter_values) if hard_filter_values else 0.0,
            by_phase={
                phase: {"recall_at_k": sum(values) / len(values), "query_count": float(len(values))}
                for phase, values in phase_values.items()
            },
        )


__all__ = [
    "BeliefConflictDetector",
    "HookPrioritizer",
    "MemoryConsolidator",
    "RelationshipTrendAnalyzer",
    "RetrievalEvaluationService",
    "ThreadStagnationDetector",
]
