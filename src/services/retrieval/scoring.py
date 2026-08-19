"""Deterministic hybrid scoring for initial and targeted retrieval."""

from __future__ import annotations

import math
import re

from src.application.contracts.retrieval import MemoryCandidate, RetrievalQuery, ScoreBreakdown

_TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _tokens(value: str) -> frozenset[str]:
    return frozenset(token.casefold() for token in _TOKEN_PATTERN.findall(value))


class RetrievalScorer:
    """Score only candidates already admitted by :class:`HardScopeFilter`."""

    def __init__(self, *, recency_half_life: float = 12.0) -> None:
        if recency_half_life <= 0:
            raise ValueError("Recency half-life must be positive.")
        self.recency_half_life = recency_half_life

    def score(self, candidate: MemoryCandidate, query: RetrievalQuery) -> ScoreBreakdown:
        if query.scope is None:
            raise ValueError("Retrieval scoring requires a RetrievalScope.")
        age = max(0, query.scope.world_time - candidate.world_time)
        recency = math.exp(-age / self.recency_half_life)
        entity_match = self._overlap(query.entity_ids, candidate.entity_ids)
        goal_match = self._overlap(query.goal_ids, candidate.goal_ids)
        thread_match = self._overlap(query.thread_ids, candidate.thread_ids)
        lexical_match = self._lexical_match(query.query_text, candidate.search_text)
        exact_match = self._exact_match(candidate, query)

        total = _clamp(
            0.15 * recency
            + 0.20 * candidate.salience
            + 0.10 * candidate.emotional_intensity
            + 0.15 * entity_match
            + 0.05 * goal_match
            + 0.05 * thread_match
            + 0.20 * lexical_match
            + 0.10 * exact_match
        )
        if exact_match:
            total = max(total, 0.98)
        return ScoreBreakdown(
            recency=_clamp(recency),
            salience=candidate.salience,
            emotional_intensity=candidate.emotional_intensity,
            entity_match=entity_match,
            goal_match=goal_match,
            thread_match=thread_match,
            lexical_match=lexical_match,
            exact_match=exact_match,
            total=total,
        )

    @staticmethod
    def _overlap(requested: tuple[str, ...], available: tuple[str, ...]) -> float:
        if not requested:
            return 0.0
        requested_set = set(requested)
        available_set = set(available)
        return len(requested_set & available_set) / len(requested_set)

    @staticmethod
    def _lexical_match(query_text: str, candidate_text: str) -> float:
        query_tokens = _tokens(query_text)
        if not query_tokens:
            return 0.0
        candidate_tokens = _tokens(candidate_text)
        return len(query_tokens & candidate_tokens) / len(query_tokens)

    @staticmethod
    def _exact_match(candidate: MemoryCandidate, query: RetrievalQuery) -> float:
        if query.target_claim_ids and (
            candidate.claim_id in query.target_claim_ids or candidate.source_id in query.target_claim_ids
        ):
            return 1.0
        if query.fingerprint and candidate.normalized_fingerprint == query.fingerprint:
            return 1.0
        if query.predicate and candidate.predicate != query.predicate:
            return 0.0
        if query.subject_id and candidate.subject_id != query.subject_id:
            return 0.0
        if query.object_id is not None and candidate.object_id != query.object_id:
            return 0.0
        if query.typed_value is not None and candidate.typed_value != query.typed_value:
            return 0.0
        if any(value is not None for value in (query.predicate, query.subject_id, query.object_id, query.typed_value)):
            return 1.0
        return 0.0

    def reasons(self, candidate: MemoryCandidate, query: RetrievalQuery) -> tuple[str, ...]:
        breakdown = self.score(candidate, query)
        reasons: list[str] = []
        if breakdown.exact_match:
            reasons.append("exact_claim_match")
        if breakdown.entity_match:
            reasons.append("entity_match")
        if breakdown.goal_match:
            reasons.append("goal_match")
        if breakdown.thread_match:
            reasons.append("thread_match")
        if breakdown.lexical_match:
            reasons.append("lexical_match")
        if str(candidate.kind) == "event" and breakdown.recency >= 0.5:
            reasons.append("recent_event")
        if candidate.salience >= 0.75:
            reasons.append("high_salience")
        return tuple(reasons)


__all__ = ["RetrievalScorer"]
