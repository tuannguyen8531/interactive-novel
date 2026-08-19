"""Perspective-safe initial and targeted retrieval services."""

from .budget import DEFAULT_ROLE_BUDGETS, TokenBudgetAllocator, estimate_tokens
from .claims import ClaimExtractor
from .context import ContextAssembler, TargetedConsistencyRetriever
from .embeddings import InMemoryEmbeddingStore, OllamaEmbeddingIndexer, cosine_similarity
from .rebuild import EmbeddingRebuildService
from .scope import HardScopeFilter
from .scoring import RetrievalScorer
from .sources import (
    belief_to_candidate,
    claim_to_candidate,
    event_to_candidate,
    hook_to_candidate,
    observation_to_candidate,
    summary_to_candidate,
    thread_to_candidate,
)
from .tracing import InMemoryRetrievalTraceStore

__all__ = [
    "DEFAULT_ROLE_BUDGETS",
    "ClaimExtractor",
    "ContextAssembler",
    "HardScopeFilter",
    "InMemoryEmbeddingStore",
    "EmbeddingRebuildService",
    "InMemoryRetrievalTraceStore",
    "OllamaEmbeddingIndexer",
    "RetrievalScorer",
    "TokenBudgetAllocator",
    "TargetedConsistencyRetriever",
    "belief_to_candidate",
    "claim_to_candidate",
    "cosine_similarity",
    "estimate_tokens",
    "event_to_candidate",
    "hook_to_candidate",
    "observation_to_candidate",
    "summary_to_candidate",
    "thread_to_candidate",
]
