"""Role-aware deterministic token budgeting."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from src.application.contracts.retrieval import RetrievalHit

DEFAULT_ROLE_BUDGETS: dict[str, int] = {
    "world_builder": 2_000,
    "planner": 2_500,
    "simulator": 3_500,
    "validator": 4_000,
    "writer": 2_000,
    "critic": 2_200,
    "memory": 1_500,
    "embedding": 1_000,
}


def estimate_tokens(text: str) -> int:
    """Use a stable conservative estimate without requiring a tokenizer."""
    return max(1, (len(text.strip()) + 3) // 4)


class TokenBudgetAllocator:
    """Select ranked context items without exceeding a role budget."""

    def __init__(self, role_budgets: dict[str, int] | None = None) -> None:
        self.role_budgets = dict(DEFAULT_ROLE_BUDGETS)
        if role_budgets:
            self.role_budgets.update(role_budgets)
        if any(value <= 0 for value in self.role_budgets.values()):
            raise ValueError("Role token budgets must be positive.")

    def budget_for(self, role: str, override: int | None = None) -> int:
        budget = override if override is not None else self.role_budgets.get(role, self.role_budgets["planner"])
        if budget <= 0:
            raise ValueError("Token budget must be positive.")
        return budget

    def select(
        self,
        hits: Sequence[RetrievalHit],
        *,
        role: str,
        token_budget: int | None = None,
        max_items: int | None = None,
    ) -> tuple[tuple[RetrievalHit, ...], tuple[tuple[str, int], ...], int]:
        budget = self.budget_for(role, token_budget)
        selected: list[RetrievalHit] = []
        dropped: list[tuple[str, int]] = []
        used = 0
        for hit in hits:
            if max_items is not None and len(selected) >= max_items:
                dropped.append((hit.source_id, 0))
                continue
            estimate = estimate_tokens(hit.candidate.text)
            if used + estimate > budget:
                dropped.append((hit.source_id, estimate))
                continue
            selected.append(hit)
            used += estimate
        return tuple(selected), tuple(dropped), used

    def allocate(self, texts: Iterable[str], *, role: str, token_budget: int | None = None) -> tuple[tuple[str, ...], int]:
        """Small utility for callers that only have text rather than hits."""
        budget = self.budget_for(role, token_budget)
        selected: list[str] = []
        used = 0
        for text in texts:
            estimate = estimate_tokens(text)
            if used + estimate > budget:
                break
            selected.append(text)
            used += estimate
        return tuple(selected), used


__all__ = ["DEFAULT_ROLE_BUDGETS", "TokenBudgetAllocator", "estimate_tokens"]
