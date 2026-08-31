"""Deterministic content, age and consent policy enforcement."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from .errors import DomainValidationError


class Rating(StrEnum):
    TEEN_14_PLUS = "teen_14_plus"
    MATURE_16_PLUS = "mature_16_plus"
    ADULT_18_PLUS = "adult_18_plus"


class ViolenceCeiling(StrEnum):
    NONE = "none"
    RESTRAINED = "restrained"
    DETAILED = "detailed"

    @classmethod
    def _missing_(cls, value: object) -> ViolenceCeiling | None:
        legacy = {"non_graphic": cls.RESTRAINED, "graphic": cls.DETAILED}
        return legacy.get(str(value))


class ContentDecision(StrEnum):
    ALLOW = "allow"
    DOWNGRADE = "downgrade"
    DENY = "deny"


class ConsentState(StrEnum):
    NOT_DISCUSSED = "not_discussed"
    REQUESTED = "requested"
    GRANTED = "granted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


CONSENT_TRANSITIONS: dict[ConsentState, set[ConsentState]] = {
    ConsentState.NOT_DISCUSSED: {ConsentState.REQUESTED},
    ConsentState.REQUESTED: {ConsentState.GRANTED, ConsentState.DECLINED},
    ConsentState.GRANTED: {ConsentState.WITHDRAWN},
    ConsentState.DECLINED: {ConsentState.REQUESTED},
    ConsentState.WITHDRAWN: {ConsentState.REQUESTED},
}

KNOWN_CONTENT_TAGS = {
    "romantic_affection",
    "dating",
    "kiss",
    "non_graphic_intimacy",
    "mature_emotional_theme",
    "sexual_reference_fade_to_black",
    "adult_explicit",
    "sexualized_nudity",
    "fetishization",
    "grooming",
    "exploitation",
    "non_consensual_sexual",
    "violence",
    "violence:torture",
    "sexual_violence",
    # Legacy tags remain readable for persisted scene artifacts.
    "violence_non_graphic",
    "violence_gore",
    "violence_torture_detail",
    "violence_sexual",
    "psychological_harm",
    "loss",
    "complex_relationship",
}


@dataclass(frozen=True, slots=True)
class ConsentRequirements:
    required: bool = False
    explicit_affirmative: bool = True
    withdrawal_supported: bool = True


@dataclass(frozen=True, slots=True)
class ContentPolicy:
    schema_version: str = "content"
    rating: Rating = Rating.TEEN_14_PLUS
    violence_ceiling: ViolenceCeiling = ViolenceCeiling.RESTRAINED
    consent: ConsentRequirements = field(default_factory=ConsentRequirements)

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise DomainValidationError("invalid_content_policy", "Content policy schema version cannot be empty.")
        object.__setattr__(self, "rating", Rating(self.rating))
        object.__setattr__(self, "violence_ceiling", ViolenceCeiling(self.violence_ceiling))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> ContentPolicy:
        consent = mapping.get("consent", {})
        return cls(
            schema_version=str(mapping.get("schema_version", "content")),
            rating=Rating(mapping.get("rating", Rating.TEEN_14_PLUS)),
            violence_ceiling=ViolenceCeiling(mapping.get("violence_ceiling", ViolenceCeiling.RESTRAINED)),
            consent=ConsentRequirements(
                required=bool(consent.get("required", False)),
                explicit_affirmative=bool(consent.get("explicit_affirmative", True)),
                withdrawal_supported=bool(consent.get("withdrawal_supported", True)),
            ),
        )


@dataclass(frozen=True, slots=True)
class SceneSpec:
    """Structured scene proposal evaluated before any prose writer sees it."""

    world_time: int
    tags: tuple[str, ...] = ()
    participants: Mapping[str, int] = field(default_factory=dict)
    consent: Mapping[str, ConsentState | str] = field(default_factory=dict)
    violence_detail: ViolenceCeiling = ViolenceCeiling.NONE
    scene_id: str = "scene-proposal"

    def __post_init__(self) -> None:
        if isinstance(self.world_time, bool) or not isinstance(self.world_time, int) or self.world_time < 0:
            raise DomainValidationError("invalid_world_time", "Scene world time must be non-negative.")
        normalized_tags = tuple(str(tag) for tag in self.tags)
        if any(not tag for tag in normalized_tags):
            raise DomainValidationError("invalid_content_tag", "Scene tags cannot be empty.")
        normalized_participants: dict[str, int] = {}
        for participant_id, age in self.participants.items():
            if not str(participant_id).strip() or isinstance(age, bool) or not isinstance(age, int) or age < 0:
                raise DomainValidationError("invalid_participant_age", "Scene participant IDs and ages must be valid.")
            normalized_participants[str(participant_id)] = age
        normalized_consent = {str(key): ConsentState(value) for key, value in self.consent.items()}
        object.__setattr__(self, "tags", normalized_tags)
        object.__setattr__(self, "participants", normalized_participants)
        object.__setattr__(self, "consent", normalized_consent)
        object.__setattr__(self, "violence_detail", ViolenceCeiling(self.violence_detail))

    @classmethod
    def from_profiles(
        cls,
        *,
        world_time: int,
        profiles: Mapping[str, Any],
        tags: tuple[str, ...] = (),
        consent: Mapping[str, ConsentState | str] | None = None,
        violence_detail: ViolenceCeiling | str = ViolenceCeiling.NONE,
        scene_id: str = "scene-proposal",
    ) -> SceneSpec:
        participants = {character_id: profile.age_at(world_time) for character_id, profile in profiles.items()}
        return cls(
            world_time=world_time,
            tags=tags,
            participants=participants,
            consent=consent or {},
            violence_detail=ViolenceCeiling(violence_detail),
            scene_id=scene_id,
        )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision: ContentDecision
    reason_codes: tuple[str, ...]
    effective_policy_version: str
    participant_ages: Mapping[str, int]
    evaluated_tags: tuple[str, ...]
    evaluated_world_time: int
    safe_tags: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.decision in {ContentDecision.ALLOW, ContentDecision.DOWNGRADE}

    @property
    def reason_code(self) -> str | None:
        return self.reason_codes[0] if self.reason_codes else None


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    scene_id: str
    participant_id: str
    activity_tag: str
    state: ConsentState = ConsentState.NOT_DISCUSSED
    requested_at: int | None = None
    decided_at: int | None = None

    def transition(self, next_state: ConsentState | str, *, world_time: int) -> ConsentRecord:
        next_value = ConsentState(next_state)
        if next_value not in CONSENT_TRANSITIONS[self.state]:
            raise DomainValidationError(
                "invalid_consent_transition",
                f"Consent cannot transition from {self.state} to {next_value}.",
            )
        if world_time < 0:
            raise DomainValidationError("invalid_world_time", "Consent transition time cannot be negative.")
        requested_at = self.requested_at
        if next_value == ConsentState.REQUESTED:
            requested_at = world_time
        decided_at = (
            world_time if next_value in {ConsentState.GRANTED, ConsentState.DECLINED, ConsentState.WITHDRAWN} else self.decided_at
        )
        return replace(self, state=next_value, requested_at=requested_at, decided_at=decided_at)


def _decision(
    policy: ContentPolicy,
    scene: SceneSpec,
    decision: ContentDecision,
    *reason_codes: str,
    safe_tags: tuple[str, ...] = (),
) -> PolicyDecision:
    return PolicyDecision(
        decision=decision,
        reason_codes=tuple(reason_codes),
        effective_policy_version=policy.schema_version,
        participant_ages=dict(scene.participants),
        evaluated_tags=scene.tags,
        evaluated_world_time=scene.world_time,
        safe_tags=safe_tags,
    )


def evaluate_scene(policy: ContentPolicy, scene: SceneSpec) -> PolicyDecision:
    """Evaluate a scene in the documented deterministic order."""
    unknown_tags = sorted(set(scene.tags) - KNOWN_CONTENT_TAGS)
    if unknown_tags or not scene.participants:
        return _decision(policy, scene, ContentDecision.DENY, "schema_or_tag_invalid")
    if any(age < 14 for age in scene.participants.values()):
        return _decision(policy, scene, ContentDecision.DENY, "participant_age_below_policy_minimum")

    tags = set(scene.tags)
    ages = tuple(scene.participants.values())
    adult_minor_romance = (
        any(age >= 18 for age in ages)
        and any(age < 18 for age in ages)
        and bool(tags & {"romantic_affection", "dating", "kiss", "non_graphic_intimacy", "mature_emotional_theme"})
    )
    if adult_minor_romance:
        return _decision(policy, scene, ContentDecision.DENY, "adult_minor_romance_not_allowed")

    explicit = bool(tags & {"adult_explicit", "sexualized_nudity", "fetishization"})
    sexual_violence = bool(tags & {"sexual_violence", "non_consensual_sexual", "violence_sexual"})
    if sexual_violence and any(age < 18 for age in ages):
        return _decision(policy, scene, ContentDecision.DENY, "sexual_violence_participant_under_18")
    if tags & {"non_graphic_intimacy", "sexual_reference_fade_to_black"} and any(age < 16 for age in ages):
        return _decision(policy, scene, ContentDecision.DENY, "age_14_15_non_sexual")
    if explicit and any(age < 16 for age in ages):
        return _decision(policy, scene, ContentDecision.DENY, "age_14_15_explicit_not_allowed")
    if explicit and any(16 <= age < 18 for age in ages):
        if policy.rating == Rating.ADULT_18_PLUS:
            return _decision(policy, scene, ContentDecision.DENY, "age_16_17_explicit_not_allowed")
        return _decision(
            policy,
            scene,
            ContentDecision.DOWNGRADE,
            "age_16_17_non_explicit",
            safe_tags=("non_graphic_intimacy",),
        )

    violence_tags = tags & {
        "violence",
        "violence:torture",
        "sexual_violence",
        "non_consensual_sexual",
        "violence_non_graphic",
        "violence_gore",
        "violence_torture_detail",
        "violence_sexual",
    }
    if violence_tags:
        detail = scene.violence_detail
        if tags & {"violence_gore", "violence_torture_detail", "violence_sexual"}:
            detail = ViolenceCeiling.DETAILED
        elif "violence_non_graphic" in tags and detail == ViolenceCeiling.NONE:
            detail = ViolenceCeiling.RESTRAINED
        detail_rank = {
            ViolenceCeiling.NONE: 0,
            ViolenceCeiling.RESTRAINED: 1,
            ViolenceCeiling.DETAILED: 2,
        }
        if detail == ViolenceCeiling.NONE or detail_rank[detail] > detail_rank[policy.violence_ceiling]:
            return _decision(policy, scene, ContentDecision.DENY, "violence_over_ceiling")

    if sexual_violence and policy.rating != Rating.ADULT_18_PLUS:
        return _decision(policy, scene, ContentDecision.DENY, "rating_not_allowed")

    if explicit:
        if policy.rating != Rating.ADULT_18_PLUS:
            return _decision(policy, scene, ContentDecision.DENY, "rating_not_allowed")
        if policy.consent.required:
            expected_keys = {f"{participant_id}:explicit" for participant_id in scene.participants}
            states = {key: scene.consent.get(key, ConsentState.NOT_DISCUSSED) for key in expected_keys}
            if any(state == ConsentState.WITHDRAWN for state in states.values()):
                return _decision(policy, scene, ContentDecision.DENY, "consent_withdrawn")
            if any(state != ConsentState.GRANTED for state in states.values()):
                return _decision(policy, scene, ContentDecision.DENY, "consent_missing_or_invalid")

    return _decision(policy, scene, ContentDecision.ALLOW)


__all__ = [
    "CONSENT_TRANSITIONS",
    "KNOWN_CONTENT_TAGS",
    "ConsentRecord",
    "ConsentRequirements",
    "ConsentState",
    "ContentDecision",
    "ContentPolicy",
    "PolicyDecision",
    "Rating",
    "SceneSpec",
    "ViolenceCeiling",
    "evaluate_scene",
]
