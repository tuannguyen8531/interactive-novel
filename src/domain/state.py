"""In-memory canonical state consumed by the pure domain engine."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .characters import Character
from .clock import InWorldClock
from .content import ConsentRecord, ContentPolicy
from .events import Belief, Event, Evidence, Observation
from .knowledge import CanonFact, ClaimLink, KnowledgeClaim
from .narrative import NarrativeHook, NarrativeThread
from .relationships import RelationshipChange, RelationshipVector


@dataclass
class GameState:
    """Canonical state for one branch; no persistence or framework concerns."""

    world_id: str
    playthrough_id: str
    branch_id: str
    clock: InWorldClock = field(default_factory=InWorldClock)
    branch_ancestry: tuple[str, ...] = ()
    characters: dict[str, Character] = field(default_factory=dict)
    locations: set[str] = field(default_factory=set)
    relationships: dict[tuple[str, str], RelationshipVector] = field(default_factory=dict)
    relationship_changes: list[RelationshipChange] = field(default_factory=list)
    claims: dict[str, KnowledgeClaim] = field(default_factory=dict)
    claim_links: dict[str, ClaimLink] = field(default_factory=dict)
    canon_facts: dict[str, CanonFact] = field(default_factory=dict)
    events: dict[str, Event] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    observations: dict[str, Observation] = field(default_factory=dict)
    beliefs: dict[str, Belief] = field(default_factory=dict)
    threads: dict[str, NarrativeThread] = field(default_factory=dict)
    hooks: dict[str, NarrativeHook] = field(default_factory=dict)
    consents: dict[tuple[str, str, str], ConsentRecord] = field(default_factory=dict)
    policy: ContentPolicy | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.world_id.strip() or not self.playthrough_id.strip() or not self.branch_id.strip():
            raise ValueError("GameState requires world, playthrough and branch IDs.")
        if not self.branch_ancestry:
            self.branch_ancestry = (self.branch_id,)
        elif self.branch_id not in self.branch_ancestry:
            self.branch_ancestry = (*self.branch_ancestry, self.branch_id)

    @classmethod
    def empty(
        cls,
        *,
        world_id: str = "world",
        playthrough_id: str = "playthrough",
        branch_id: str = "root",
        world_time: int = 0,
        policy: ContentPolicy | None = None,
    ) -> GameState:
        return cls(
            world_id=world_id,
            playthrough_id=playthrough_id,
            branch_id=branch_id,
            clock=InWorldClock(world_time),
            policy=policy,
        )

    @property
    def world_time(self) -> int:
        return self.clock.world_time

    def copy(self) -> GameState:
        return deepcopy(self)

    def relationship_vector(self, source_id: str, target_id: str) -> RelationshipVector:
        return self.relationships.get((source_id, target_id), RelationshipVector.zero())

    def scope_is_authorized(self, branch_scope: str) -> bool:
        if branch_scope == "public" or branch_scope in self.branch_ancestry:
            return True
        root_aliases = {"root", "branch-root"}
        return branch_scope in root_aliases and bool(set(self.branch_ancestry) & root_aliases)


__all__ = ["GameState"]
