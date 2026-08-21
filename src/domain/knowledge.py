"""Typed proposition registry, claims, canon facts and evidence links."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import DomainValidationError
from .values import Provenance, TimeRange


class CanonFactStatus(StrEnum):
    ACTIVE = "active"
    RETRACTED = "retracted"
    SUPERSEDED = "superseded"


class ClaimLinkKind(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    REFINES = "refines"
    SUPERSEDES = "supersedes"


@dataclass(frozen=True, slots=True)
class PredicateDefinition:
    name: str
    subject_kind: str = "entity"
    object_kind: str | None = None
    typed_value_kind: str | None = None


DEFAULT_PREDICATES = (
    PredicateDefinition("located_at", "character", "location"),
    PredicateDefinition("age_is", "character", typed_value_kind="integer"),
    PredicateDefinition("romantic_interest", "character", "character"),
    PredicateDefinition("commitment_status", "character", "character"),
    PredicateDefinition("goal_active", "character", "goal"),
    PredicateDefinition("secret_exists", "character", "secret"),
    PredicateDefinition("item_held", "character", "item"),
    PredicateDefinition("physical_condition", "character", typed_value_kind="scalar"),
    PredicateDefinition("public_fact", "entity", typed_value_kind="scalar"),
    PredicateDefinition("event_participation", "character", "event"),
)


class PredicateRegistry:
    """Versioned finite registry; prose is never a predicate."""

    def __init__(self, predicates: Mapping[str, PredicateDefinition] | None = None, *, schema_version: str = "predicate") -> None:
        self.schema_version = schema_version
        self._predicates = dict(predicates or {predicate.name: predicate for predicate in DEFAULT_PREDICATES})

    @classmethod
    def default(cls) -> PredicateRegistry:
        return cls()

    def get(self, predicate: str) -> PredicateDefinition | None:
        return self._predicates.get(predicate)

    def contains(self, predicate: str) -> bool:
        return predicate in self._predicates

    def validate(self, claim: KnowledgeClaim) -> None:
        definition = self.get(claim.predicate)
        if definition is None:
            raise DomainValidationError("predicate_not_registered", f"Predicate is not registered: {claim.predicate}.")
        if not claim.subject_id.strip():
            raise DomainValidationError("invalid_claim_subject", "Claim subject is required.")
        has_object = claim.object_id is not None
        has_value = claim.typed_value is not None
        if has_object == has_value:
            raise DomainValidationError(
                "claim_object_or_value_required", "Claim must contain exactly one object ID or typed value."
            )
        if definition.object_kind is not None and not has_object:
            raise DomainValidationError("claim_object_required", f"Predicate {claim.predicate} requires an object ID.")
        if definition.typed_value_kind is not None and not has_value:
            raise DomainValidationError("claim_typed_value_required", f"Predicate {claim.predicate} requires a typed value.")
        if definition.typed_value_kind == "integer" and not isinstance(claim.typed_value, int):
            raise DomainValidationError("claim_typed_value_invalid", f"Predicate {claim.predicate} requires an integer value.")


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class KnowledgeClaim:
    subject_id: str
    predicate: str
    object_id: str | None = None
    typed_value: Any = None
    polarity: str = "positive"
    qualifiers: Mapping[str, Any] = field(default_factory=dict)
    valid_time: TimeRange = field(default_factory=lambda: TimeRange(0, None))
    branch_scope: str = "public"
    schema_version: str = "claim"
    claim_type: str = "knowledge_claim"
    claim_id: str = field(default_factory=_new_id)
    provenance: Provenance | None = None
    normalized_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not self.claim_id.strip()
            or not self.subject_id.strip()
            or not self.predicate.strip()
            or not self.branch_scope.strip()
        ):
            raise DomainValidationError("invalid_claim", "Claim identity, subject, predicate and scope are required.")
        if self.polarity not in {"positive", "negative"}:
            raise DomainValidationError("invalid_claim_polarity", "Claim polarity must be positive or negative.")
        if self.object_id is not None and not self.object_id.strip():
            raise DomainValidationError("invalid_claim_object", "Claim object ID cannot be empty.")
        object.__setattr__(self, "qualifiers", dict(self.qualifiers))
        object.__setattr__(self, "normalized_fingerprint", self.compute_fingerprint())

    def normalized_payload(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "object_id": self.object_id,
            "typed_value": self.typed_value,
            "polarity": self.polarity,
            "qualifiers": self.qualifiers,
            "valid_time": {"start": self.valid_time.start, "end": self.valid_time.end},
            "branch_scope": self.branch_scope,
            "schema_version": self.schema_version,
        }

    def compute_fingerprint(self) -> str:
        try:
            encoded = json.dumps(self.normalized_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise DomainValidationError("claim_not_json_serializable", "Claim values must be JSON serializable.") from error
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CanonFact:
    claim_id: str
    source_event_or_rule: str
    asserted_world_time: int
    fact_id: str = field(default_factory=_new_id)
    status: CanonFactStatus = CanonFactStatus.ACTIVE
    asserted_turn: str | None = None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        if not self.fact_id.strip() or not self.claim_id.strip() or not self.source_event_or_rule.strip():
            raise DomainValidationError("invalid_canon_fact", "Canon fact identity and source are required.")
        if self.asserted_world_time < 0:
            raise DomainValidationError("invalid_world_time", "Canon fact time cannot be negative.")
        object.__setattr__(self, "status", CanonFactStatus(self.status))


@dataclass(frozen=True, slots=True)
class ClaimLink:
    from_claim_id: str
    to_claim_id: str
    kind: ClaimLinkKind
    link_id: str = field(default_factory=_new_id)

    def __post_init__(self) -> None:
        if self.from_claim_id == self.to_claim_id:
            raise DomainValidationError("invalid_claim_link", "A claim cannot link to itself.")
        object.__setattr__(self, "kind", ClaimLinkKind(self.kind))

    @property
    def source_claim_id(self) -> str:
        return self.from_claim_id

    @property
    def target_claim_id(self) -> str:
        return self.to_claim_id


__all__ = [
    "CanonFact",
    "CanonFactStatus",
    "ClaimLink",
    "ClaimLinkKind",
    "DEFAULT_PREDICATES",
    "KnowledgeClaim",
    "PredicateDefinition",
    "PredicateRegistry",
]
