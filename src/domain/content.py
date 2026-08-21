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


class TopicBoundary(StrEnum):
    ALLOW = "allow"
    OPT_IN = "opt_in"
    EXCLUDED = "excluded"


class ViolenceCeiling(StrEnum):
    NONE = "none"
    NON_GRAPHIC = "non_graphic"
    GRAPHIC = "graphic"


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
    required: bool = True
    explicit_affirmative: bool = True
    withdrawal_supported: bool = True


@dataclass(frozen=True, slots=True)
class ContentPolicyOverride:
    """Player constraints may tighten, never relax, a world policy."""

    adult_explicit_opt_in: bool = False
    topic_boundaries: Mapping[str, TopicBoundary] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "topic_boundaries",
            {str(tag): TopicBoundary(value) for tag, value in self.topic_boundaries.items()},
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any] | None) -> ContentPolicyOverride | None:
        if mapping is None:
            return None
        return cls(
            adult_explicit_opt_in=bool(mapping.get("adult_explicit_opt_in", False)),
            topic_boundaries={str(tag): TopicBoundary(value) for tag, value in mapping.get("topic_boundaries", {}).items()},
        )


@dataclass(frozen=True, slots=True)
class ContentPolicy:
    schema_version: str = "content"
    rating: Rating = Rating.TEEN_14_PLUS
    topic_boundaries: Mapping[str, TopicBoundary] = field(default_factory=dict)
    violence_ceiling: ViolenceCeiling = ViolenceCeiling.NON_GRAPHIC
    adult_explicit_opt_in: bool = False
    consent: ConsentRequirements = field(default_factory=ConsentRequirements)
    player_overrides: ContentPolicyOverride | None = None

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise DomainValidationError("invalid_content_policy", "Content policy schema version cannot be empty.")
        object.__setattr__(self, "rating", Rating(self.rating))
        object.__setattr__(self, "violence_ceiling", ViolenceCeiling(self.violence_ceiling))
        object.__setattr__(
            self,
            "topic_boundaries",
            {str(tag): TopicBoundary(value) for tag, value in self.topic_boundaries.items()},
        )

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, Any],
        *,
        player_overrides: Mapping[str, Any] | ContentPolicyOverride | None = None,
    ) -> ContentPolicy:
        override = (
            player_overrides
            if isinstance(player_overrides, ContentPolicyOverride)
            else ContentPolicyOverride.from_mapping(player_overrides)
        )
        consent = mapping.get("consent", {})
        return cls(
            schema_version=str(mapping.get("schema_version", "content")),
            rating=Rating(mapping.get("rating", Rating.TEEN_14_PLUS)),
            topic_boundaries={str(tag): TopicBoundary(value) for tag, value in mapping.get("topic_boundaries", {}).items()},
            violence_ceiling=ViolenceCeiling(mapping.get("violence_ceiling", ViolenceCeiling.NON_GRAPHIC)),
            adult_explicit_opt_in=bool(mapping.get("adult_explicit_opt_in", False)),
            consent=ConsentRequirements(
                required=bool(consent.get("required", True)),
                explicit_affirmative=bool(consent.get("explicit_affirmative", True)),
                withdrawal_supported=bool(consent.get("withdrawal_supported", True)),
            ),
            player_overrides=override,
        )

    def with_player_override(self, override: ContentPolicyOverride | None) -> ContentPolicy:
        return replace(self, player_overrides=override)

    def world_boundary(self, tag: str) -> TopicBoundary:
        return self.topic_boundaries.get(tag, TopicBoundary.ALLOW)

    def player_boundary(self, tag: str) -> TopicBoundary:
        if self.player_overrides is None:
            return TopicBoundary.ALLOW
        return self.player_overrides.topic_boundaries.get(tag, TopicBoundary.ALLOW)

    def effective_boundary(self, tag: str) -> tuple[TopicBoundary, str | None]:
        world = self.world_boundary(tag)
        player = self.player_boundary(tag)
        if player == TopicBoundary.EXCLUDED:
            return player, "player_topic_excluded"
        if world == TopicBoundary.EXCLUDED:
            return world, "topic_excluded"
        if (
            player == TopicBoundary.OPT_IN
            and self.player_overrides is not None
            and not self.player_overrides.adult_explicit_opt_in
        ):
            return player, "player_opt_in_required"
        return world if world != TopicBoundary.ALLOW else player, None

    @property
    def effective_adult_explicit_opt_in(self) -> bool:
        player = self.player_overrides
        return self.adult_explicit_opt_in and (player is None or player.adult_explicit_opt_in)


@dataclass(frozen=True, slots=True)
class SceneSpec:
    """Structured scene proposal evaluated before any prose writer sees it."""

    world_time: int
    tags: tuple[str, ...] = ()
    participants: Mapping[str, int] = field(default_factory=dict)
    consent: Mapping[str, ConsentState | str] = field(default_factory=dict)
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

    @classmethod
    def from_profiles(
        cls,
        *,
        world_time: int,
        profiles: Mapping[str, Any],
        tags: tuple[str, ...] = (),
        consent: Mapping[str, ConsentState | str] | None = None,
        scene_id: str = "scene-proposal",
    ) -> SceneSpec:
        participants = {character_id: profile.age_at(world_time) for character_id, profile in profiles.items()}
        return cls(
            world_time=world_time,
            tags=tags,
            participants=participants,
            consent=consent or {},
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

    explicit = "adult_explicit" in tags or "sexualized_nudity" in tags
    if explicit and any(age < 16 for age in ages):
        return _decision(policy, scene, ContentDecision.DENY, "explicit_participant_under_18")
    if explicit and any(16 <= age < 18 for age in ages):
        if policy.rating == Rating.ADULT_18_PLUS:
            return _decision(policy, scene, ContentDecision.DENY, "explicit_participant_under_18")
        return _decision(
            policy,
            scene,
            ContentDecision.DOWNGRADE,
            "age_16_17_non_explicit",
            safe_tags=("non_graphic_intimacy",),
        )

    violent_tags = tags & {"violence_gore", "violence_torture_detail", "violence_sexual"}
    if violent_tags:
        return _decision(policy, scene, ContentDecision.DENY, "violence_over_ceiling")
    if "violence_non_graphic" in tags and policy.violence_ceiling == ViolenceCeiling.NONE:
        return _decision(policy, scene, ContentDecision.DENY, "violence_over_ceiling")

    for tag in scene.tags:
        boundary, reason = policy.effective_boundary(tag)
        if boundary == TopicBoundary.EXCLUDED and reason is not None:
            return _decision(policy, scene, ContentDecision.DENY, reason)

    if explicit:
        if policy.rating != Rating.ADULT_18_PLUS:
            return _decision(policy, scene, ContentDecision.DENY, "rating_not_allowed")
        if not policy.adult_explicit_opt_in:
            return _decision(policy, scene, ContentDecision.DENY, "world_explicit_not_opted_in")
        if policy.player_overrides is not None and not policy.player_overrides.adult_explicit_opt_in:
            return _decision(policy, scene, ContentDecision.DENY, "player_explicit_not_opted_in")
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
    "ContentPolicyOverride",
    "PolicyDecision",
    "Rating",
    "SceneSpec",
    "TopicBoundary",
    "ViolenceCeiling",
    "evaluate_scene",
]
