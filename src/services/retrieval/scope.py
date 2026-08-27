"""Deterministic scope filtering for retrieval candidates."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts.retrieval import PUBLIC_OWNER, MemoryCandidate, RetrievalScope


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()


class HardScopeFilter:
    """Apply all security/temporal filters before scoring or semantic search."""

    def explain(self, candidate: MemoryCandidate, scope: RetrievalScope) -> ScopeDecision:
        reasons: list[str] = []
        if candidate.playthrough_id != scope.playthrough_id:
            reasons.append("playthrough_mismatch")
        if candidate.branch_id not in scope.allowed_branch_ids:
            reasons.append("branch_not_in_ancestry")
        owner_scoped = candidate.owner_id not in {None, PUBLIC_OWNER} and candidate.branch_scope == candidate.owner_id
        if not owner_scoped and candidate.branch_scope not in {"", PUBLIC_OWNER, *scope.allowed_branch_ids}:
            reasons.append("branch_scope_mismatch")

        if candidate.world_time > scope.world_time:
            reasons.append("future_world_time")
        if candidate.valid_time_start is not None and candidate.valid_time_start > scope.world_time:
            reasons.append("future_validity_start")
        if (
            candidate.valid_time_end is not None
            and candidate.valid_time_end < scope.world_time
            and str(candidate.kind) in {"claim", "observation", "belief"}
        ):
            # Historical events remain useful, but a typed claim that is no
            # longer valid must not be presented as current evidence. Events
            # have no validity range and therefore do not enter this branch.
            reasons.append("expired_validity")

        visibility = candidate.visibility.strip().lower()
        owner_allowed = candidate.owner_id in {None, PUBLIC_OWNER}
        if visibility in {"private", "owner", "character"} or candidate.owner_id not in {None, PUBLIC_OWNER}:
            owner_allowed = scope.owner_id is not None and candidate.owner_id == scope.owner_id
        if visibility == "public" and not scope.include_public:
            owner_allowed = scope.owner_id is not None and candidate.owner_id == scope.owner_id
        if not owner_allowed:
            reasons.append("owner_or_visibility_mismatch")

        return ScopeDecision(allowed=not reasons, reasons=tuple(reasons))

    def allows(self, candidate: MemoryCandidate, scope: RetrievalScope) -> bool:
        return self.explain(candidate, scope).allowed

    def filter(
        self,
        candidates: tuple[MemoryCandidate, ...] | list[MemoryCandidate],
        scope: RetrievalScope,
    ) -> tuple[MemoryCandidate, ...]:
        """Return only candidates allowed by the hard scope boundary."""
        return tuple(candidate for candidate in candidates if self.allows(candidate, scope))

    def filter_with_reasons(
        self,
        candidates: tuple[MemoryCandidate, ...] | list[MemoryCandidate],
        scope: RetrievalScope,
    ) -> tuple[tuple[MemoryCandidate, ScopeDecision], ...]:
        return tuple((candidate, self.explain(candidate, scope)) for candidate in candidates)


__all__ = ["HardScopeFilter", "ScopeDecision"]
