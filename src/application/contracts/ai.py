"""Versioned, provider-neutral contracts for the AI roles.

These models describe proposals and artifacts crossing the application/provider
boundary. They do not grant authority to mutate the domain; authoritative
changes are represented only by typed claims and typed state operations.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AIPromptRole(StrEnum):
    WORLD_BUILDER = "world_builder"
    PLANNER = "planner"
    SIMULATOR = "simulator"
    CONTEXT_VALIDATOR = "context_validator"
    WRITER = "writer"
    CRITIC = "critic"


class ThreadAction(StrEnum):
    ADVANCE = "advance"
    DEFER = "defer"


class ClaimPolarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class ClaimLinkKind(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    REFINES = "refines"
    SUPERSEDES = "supersedes"


class ConsistencyStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CritiqueDecision(StrEnum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"


class ConsentStateValue(StrEnum):
    NOT_DISCUSSED = "not_discussed"
    REQUESTED = "requested"
    GRANTED = "granted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class TopicBoundaryValue(StrEnum):
    ALLOW = "allow"
    OPT_IN = "opt_in"
    EXCLUDED = "excluded"


class RatingValue(StrEnum):
    TEEN_14_PLUS = "teen_14_plus"
    MATURE_16_PLUS = "mature_16_plus"
    ADULT_18_PLUS = "adult_18_plus"


class ViolenceCeilingValue(StrEnum):
    NONE = "none"
    NON_GRAPHIC = "non_graphic"
    GRAPHIC = "graphic"


ParseStatus = Literal["not_parsed", "parsed", "repaired", "failed"]


class RelationshipDimensionValue(StrEnum):
    AFFECTION = "affection"
    ATTRACTION = "attraction"
    TRUST = "trust"
    RESPECT = "respect"
    COMFORT = "comfort"
    FEAR = "fear"
    RESENTMENT = "resentment"


REGISTERED_PREDICATES = frozenset(
    {
        "located_at",
        "age_is",
        "romantic_interest",
        "commitment_status",
        "goal_active",
        "secret_exists",
        "item_held",
        "physical_condition",
        "public_fact",
        "event_participation",
    }
)
RegisteredPredicate = Literal[
    "located_at",
    "age_is",
    "romantic_interest",
    "commitment_status",
    "goal_active",
    "secret_exists",
    "item_held",
    "physical_condition",
    "public_fact",
    "event_participation",
]


class AIModel(BaseModel):
    """Strict base for data parsed from an AI response."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class VersionedOutput(AIModel):
    """Common trace metadata carried by every role output."""

    schema_version: str = Field(min_length=1)
    role: AIPromptRole
    run_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    physical_call_id: str | None = Field(default=None, min_length=1)
    config_snapshot_id: str | None = Field(default=None, min_length=1)
    expected_schema_version: ClassVar[str] = ""
    expected_role: ClassVar[AIPromptRole]

    @field_validator("schema_version")
    @classmethod
    def schema_version_matches_contract(cls, value: str) -> str:
        if value != cls.expected_schema_version:
            raise ValueError(f"expected schema version {cls.expected_schema_version!r}, received {value!r}")
        return value


class TokenUsageSnapshot(AIModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class LLMRunTrace(AIModel):
    """Metadata needed to audit an AI proposal without storing raw prompt/output."""

    schema_version: str = "llm-run-trace"
    run_id: str = Field(min_length=1)
    logical_role: AIPromptRole
    physical_call_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    request_id: str | None = Field(default=None, min_length=1)
    prompt_version: str = Field(min_length=1)
    output_schema_version: str = Field(min_length=1)
    config_snapshot_id: str | None = Field(default=None, min_length=1)
    latency_ms: float = Field(ge=0.0)
    token_usage: TokenUsageSnapshot | None = None
    finish_reason: str | None = Field(default=None, min_length=1)
    retry_count: int = Field(default=0, ge=0)
    fallback_from: str | None = Field(default=None, min_length=1)
    parse_status: ParseStatus = "not_parsed"
    raw_output_stored: bool = False


class RoleInput(AIModel):
    """Versioned envelope for role-specific context assembled by the graph."""

    input_schema_version: str = Field(min_length=1)
    role: AIPromptRole
    run_id: str = Field(min_length=1)
    context_manifest_id: str = Field(min_length=1)
    branch_id: str = Field(min_length=1)
    world_time: int = Field(ge=0)
    context: dict[str, Any] = Field(default_factory=dict)


class AIProvenance(AIModel):
    source_type: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    model_metadata: dict[str, Any] = Field(default_factory=dict)


class TimeWindow(AIModel):
    start: int = Field(ge=0)
    end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def end_follows_start(self) -> Self:
        if self.end is not None and self.end < self.start:
            raise ValueError("time window end cannot precede start")
        return self


class Beat(AIModel):
    beat_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    actor_ids: tuple[str, ...] = Field(default_factory=tuple)
    location_id: str | None = Field(default=None, min_length=1)
    required: bool = False


class ThreadDirective(AIModel):
    thread_id: str = Field(min_length=1)
    action: ThreadAction
    reason: str = Field(min_length=1)


class RequiredCheck(AIModel):
    check_id: str = Field(min_length=1)
    check_type: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class OutcomeCandidate(AIModel):
    outcome_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    likelihood: float = Field(ge=0.0, le=1.0)
    risk_flags: tuple[str, ...] = Field(default_factory=tuple)


class TurnPlan(VersionedOutput):
    """Planner output: direction and checks, never an authoritative mutation."""

    expected_schema_version: ClassVar[str] = "turn-plan"
    expected_role: ClassVar[AIPromptRole] = AIPromptRole.PLANNER
    interpreted_player_intent: str = Field(min_length=1)
    candidate_beats: tuple[Beat, ...] = Field(min_length=1)
    intended_focus: tuple[str, ...] = Field(min_length=1)
    thread_directives: tuple[ThreadDirective, ...] = Field(default_factory=tuple)
    characters_involved: tuple[str, ...] = Field(min_length=1)
    stakes: tuple[str, ...] = Field(default_factory=tuple)
    required_checks: tuple[RequiredCheck, ...] = Field(default_factory=tuple)
    possible_outcomes: tuple[OutcomeCandidate, ...] = Field(min_length=1)
    pacing_note: str = Field(min_length=1)
    safety_constraints: tuple[str, ...] = Field(default_factory=tuple)


class NPCReaction(AIModel):
    character_id: str = Field(min_length=1)
    immediate_reaction: str = Field(min_length=1)
    agency_goal: str = Field(min_length=1)
    resistance_or_agreement: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class UncertaintyNote(AIModel):
    subject_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class KnowledgeClaimProposal(AIModel):
    """Typed proposition; prose cannot substitute for this structure."""

    schema_version: Literal["knowledge-claim-proposal"] = "knowledge-claim-proposal"
    proposal_id: str = Field(min_length=1)
    source_role: AIPromptRole
    source_run_id: str = Field(min_length=1)
    claim_type: Literal["knowledge_claim"] = "knowledge_claim"
    subject_id: str = Field(min_length=1)
    predicate: RegisteredPredicate
    object_id: str | None = Field(default=None, min_length=1)
    typed_value: Any = None
    polarity: ClaimPolarity = ClaimPolarity.POSITIVE
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    valid_time: TimeWindow = Field(default_factory=lambda: TimeWindow(start=0))
    branch_scope: str = Field(min_length=1)
    provenance: AIProvenance

    @model_validator(mode="after")
    def validate_proposition_shape(self) -> Self:
        if self.predicate not in REGISTERED_PREDICATES:
            raise ValueError(f"predicate is not registered: {self.predicate}")
        has_object = self.object_id is not None
        has_value = self.typed_value is not None
        if has_object == has_value:
            raise ValueError("claim must contain exactly one of object_id or typed_value")
        object_predicates = {
            "located_at",
            "romantic_interest",
            "commitment_status",
            "goal_active",
            "secret_exists",
            "item_held",
            "event_participation",
        }
        if self.predicate in object_predicates and not has_object:
            raise ValueError(f"predicate {self.predicate} requires object_id")
        if self.predicate == "age_is" and (not isinstance(self.typed_value, int) or isinstance(self.typed_value, bool)):
            raise ValueError("predicate age_is requires an integer typed_value")
        return self


class ClaimLinkProposal(AIModel):
    schema_version: Literal["claim-link-proposal"] = "claim-link-proposal"
    from_claim_id: str = Field(min_length=1)
    to_claim_id: str = Field(min_length=1)
    kind: ClaimLinkKind

    @model_validator(mode="after")
    def cannot_link_to_self(self) -> Self:
        if self.from_claim_id == self.to_claim_id:
            raise ValueError("claim link cannot point to itself")
        return self


class KnowledgeRequirement(AIModel):
    """Perspective-aware request for evidence, not an assertion of truth."""

    schema_version: Literal["knowledge-requirement"] = "knowledge-requirement"
    requirement_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    predicate: RegisteredPredicate
    object_id: str | None = Field(default=None, min_length=1)
    typed_value: Any = None
    purpose: str = Field(min_length=1)
    branch_scope: str = Field(min_length=1)
    world_time: int = Field(ge=0)
    minimum_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_requested_proposition(self) -> Self:
        if self.predicate not in REGISTERED_PREDICATES:
            raise ValueError(f"predicate is not registered: {self.predicate}")
        if (self.object_id is None) == (self.typed_value is None):
            raise ValueError("knowledge requirement must contain exactly one of object_id or typed_value")
        return self


class ValidationQuery(AIModel):
    schema_version: Literal["validation-query"] = "validation-query"
    query_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    query_type: Literal["authorization", "consistency", "knowledge_visibility", "timeline"]
    question: str = Field(min_length=1)
    branch_scope: str = Field(min_length=1)
    world_time: int = Field(ge=0)
    target_claim_ids: tuple[str, ...] = Field(default_factory=tuple)


class EvidenceReference(AIModel):
    evidence_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    branch_scope: str = Field(min_length=1)
    world_time: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)
    match_reason: str = Field(min_length=1)


class TargetedEvidenceManifest(AIModel):
    schema_version: Literal["targeted-evidence-manifest"] = "targeted-evidence-manifest"
    query_id: str = Field(min_length=1)
    branch_scope: str = Field(min_length=1)
    world_time: int = Field(ge=0)
    evidence: tuple[EvidenceReference, ...] = Field(default_factory=tuple)
    insufficient_evidence: bool = False
    retrieval_trace_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_status_is_explicit(self) -> Self:
        if not self.evidence and not self.insufficient_evidence:
            raise ValueError("empty targeted evidence must be marked insufficient_evidence")
        if self.evidence and self.insufficient_evidence:
            raise ValueError("manifest cannot contain evidence and be marked insufficient")
        return self


class ConsistencyViolation(AIModel):
    violation_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    severity: DiagnosticSeverity
    description: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)


class ConsistencyReport(VersionedOutput):
    expected_schema_version: ClassVar[str] = "consistency-report"
    expected_role: ClassVar[AIPromptRole] = AIPromptRole.CONTEXT_VALIDATOR
    status: ConsistencyStatus
    violations: tuple[ConsistencyViolation, ...] = Field(default_factory=tuple)
    evidence_manifest_ids: tuple[str, ...] = Field(default_factory=tuple)
    recommended_corrections: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def pass_requires_no_blocking_violation(self) -> Self:
        blocking = {DiagnosticSeverity.ERROR, DiagnosticSeverity.CRITICAL}
        if self.status == ConsistencyStatus.PASS and any(item.severity in blocking for item in self.violations):
            raise ValueError("consistency report cannot PASS with error or critical violations")
        if self.status == ConsistencyStatus.INSUFFICIENT_EVIDENCE and not self.recommended_corrections:
            raise ValueError("insufficient_evidence report requires a diagnostic correction or next step")
        return self


class AdvanceClockOperation(AIModel):
    operation_type: Literal["advance_clock"] = "advance_clock"
    duration_minutes: int = Field(gt=0)


class SetCharacterLocationOperation(AIModel):
    operation_type: Literal["set_character_location"] = "set_character_location"
    character_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)


class SetCharacterConditionOperation(AIModel):
    operation_type: Literal["set_character_condition"] = "set_character_condition"
    character_id: str = Field(min_length=1)
    condition: str = Field(min_length=1)


class UpdatePsychologyOperation(AIModel):
    operation_type: Literal["update_psychology"] = "update_psychology"
    character_id: str = Field(min_length=1)
    deltas: dict[str, float] = Field(min_length=1)


class ApplyRelationshipDeltaOperation(AIModel):
    operation_type: Literal["relationship_delta"] = "relationship_delta"
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    dimension: RelationshipDimensionValue
    proposed_delta: float
    cause_event_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class AddKnowledgeClaimOperation(AIModel):
    operation_type: Literal["add_knowledge_claim"] = "add_knowledge_claim"
    claim: KnowledgeClaimProposal


class AddClaimLinkOperation(AIModel):
    operation_type: Literal["add_claim_link"] = "add_claim_link"
    link: ClaimLinkProposal


class AssertCanonFactOperation(AIModel):
    operation_type: Literal["assert_canon_fact"] = "assert_canon_fact"
    claim_id: str = Field(min_length=1)
    source_event_or_rule: str = Field(min_length=1)


class ObservationProposal(AIModel):
    observation_id: str = Field(min_length=1)
    observer_id: str = Field(min_length=1)
    observed_claim_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    method: Literal["saw", "heard", "told", "inferred"]
    branch_scope: str = Field(min_length=1)
    world_time: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    distortion: float = Field(ge=0.0, le=1.0)


class AddObservationOperation(AIModel):
    operation_type: Literal["add_observation"] = "add_observation"
    observation: ObservationProposal


class BeliefProposal(AIModel):
    belief_id: str = Field(min_length=1)
    believer_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    stance: Literal["supports", "rejects", "uncertain"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    counter_evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    branch_scope: str = Field(min_length=1)
    world_time: int = Field(ge=0)
    source_reliability: float = Field(ge=0.0, le=1.0)


class UpdateBeliefOperation(AIModel):
    operation_type: Literal["update_belief"] = "update_belief"
    belief: BeliefProposal


class TransitionThreadOperation(AIModel):
    operation_type: Literal["transition_thread"] = "transition_thread"
    thread_id: str = Field(min_length=1)
    status: Literal["seeded", "active", "escalating", "resolved", "abandoned"]
    progress_delta: float = Field(default=0.0, ge=-1.0, le=1.0)


class ConsentTransitionOperation(AIModel):
    operation_type: Literal["consent_transition"] = "consent_transition"
    scene_id: str = Field(min_length=1)
    participant_id: str = Field(min_length=1)
    activity_tag: str = Field(min_length=1)
    next_state: ConsentStateValue


StateOperation = Annotated[
    AdvanceClockOperation
    | SetCharacterLocationOperation
    | SetCharacterConditionOperation
    | UpdatePsychologyOperation
    | ApplyRelationshipDeltaOperation
    | AddKnowledgeClaimOperation
    | AddClaimLinkOperation
    | AssertCanonFactOperation
    | AddObservationOperation
    | UpdateBeliefOperation
    | TransitionThreadOperation
    | ConsentTransitionOperation,
    Field(discriminator="operation_type"),
]


class StatePatchProposal(AIModel):
    """Only typed operations may cross the authority boundary."""

    schema_version: Literal["state-patch-proposal"] = "state-patch-proposal"
    patch_id: str = Field(min_length=1)
    branch_id: str = Field(min_length=1)
    base_world_time: int = Field(ge=0)
    operations: tuple[StateOperation, ...] = Field(min_length=1)
    provenance: AIProvenance


class SimulationResult(VersionedOutput):
    expected_schema_version: ClassVar[str] = "simulation-result"
    expected_role: ClassVar[AIPromptRole] = AIPromptRole.SIMULATOR
    npc_reactions: tuple[NPCReaction, ...] = Field(min_length=1)
    proposed_outcome: str = Field(min_length=1)
    claim_proposals: tuple[KnowledgeClaimProposal, ...] = Field(default_factory=tuple)
    state_patch: StatePatchProposal | None = None
    knowledge_requirements: tuple[KnowledgeRequirement, ...] = Field(default_factory=tuple)
    uncertainties: tuple[UncertaintyNote, ...] = Field(default_factory=tuple)


class ClaimReference(AIModel):
    claim_id: str | None = Field(default=None, min_length=1)
    fingerprint: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_one_reference(self) -> Self:
        if (self.claim_id is None) == (self.fingerprint is None):
            raise ValueError("claim reference requires exactly one of claim_id or fingerprint")
        return self


class SceneSpec(AIModel):
    """Guard-facing scene artifact; Writer must not receive raw database state."""

    schema_version: Literal["scene-spec"] = "scene-spec"
    scene_id: str = Field(min_length=1)
    source_role: AIPromptRole
    source_run_id: str = Field(min_length=1)
    guard_approved: bool = False
    world_time: int = Field(ge=0)
    tags: tuple[str, ...] = Field(min_length=1)
    participants: dict[str, int] = Field(min_length=1)
    consent: dict[str, ConsentStateValue] = Field(default_factory=dict)
    approved_beats: tuple[str, ...] = Field(min_length=1)
    visible_actions: tuple[str, ...] = Field(min_length=1)
    allowed_dialogue_intents: tuple[str, ...] = Field(default_factory=tuple)
    pov: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    continuity_details: tuple[str, ...] = Field(default_factory=tuple)
    allowed_claims: tuple[ClaimReference, ...] = Field(default_factory=tuple)
    forbidden_claims: tuple[ClaimReference, ...] = Field(default_factory=tuple)
    length_target: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_participants(self) -> Self:
        if any(not character_id.strip() or age < 0 for character_id, age in self.participants.items()):
            raise ValueError("scene participants require non-empty IDs and non-negative ages")
        if any(not tag.strip() for tag in self.tags):
            raise ValueError("scene tags cannot be empty")
        return self


class ParagraphMapping(AIModel):
    paragraph_index: int = Field(ge=0)
    beat_id: str = Field(min_length=1)


class PlayerMoveSuggestion(AIModel):
    """A non-authoritative example of what the player could try next."""

    kind: Literal["act", "speak", "observe", "think"]
    text: str = Field(min_length=1, max_length=500)


class NarrativeDraft(VersionedOutput):
    """Writer prose and non-authoritative next-move examples."""

    expected_schema_version: ClassVar[str] = "narrative-draft"
    expected_role: ClassVar[AIPromptRole] = AIPromptRole.WRITER
    scene_id: str = Field(min_length=1)
    narrative_text: str = Field(min_length=1)
    paragraph_mappings: tuple[ParagraphMapping, ...] = Field(default_factory=tuple)
    disclosed_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    suggested_actions: tuple[PlayerMoveSuggestion, ...] = Field(default_factory=tuple, max_length=4)


class CritiqueIssue(AIModel):
    issue_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: DiagnosticSeverity
    description: str = Field(min_length=1)
    paragraph_index: int | None = Field(default=None, ge=0)


class CritiqueResult(VersionedOutput):
    expected_schema_version: ClassVar[str] = "critique-result"
    expected_role: ClassVar[AIPromptRole] = AIPromptRole.CRITIC
    scene_id: str = Field(min_length=1)
    decision: CritiqueDecision
    issues: tuple[CritiqueIssue, ...] = Field(default_factory=tuple)
    revision_instructions: tuple[str, ...] = Field(default_factory=tuple)
    checked_scene_spec_version: Literal["scene-spec"] = "scene-spec"

    @model_validator(mode="after")
    def revision_requires_instructions(self) -> Self:
        if self.decision == CritiqueDecision.REVISE and not self.revision_instructions:
            raise ValueError("critique decision revise requires revision_instructions")
        return self


class ContentBoundaryProposal(AIModel):
    rating: RatingValue
    topic_boundaries: dict[str, TopicBoundaryValue] = Field(default_factory=dict)
    violence_ceiling: ViolenceCeilingValue
    adult_explicit_opt_in: bool = False


class LocationSeed(AIModel):
    location_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class CharacterSeed(AIModel):
    character_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    age: int = Field(ge=14)
    role: str = Field(min_length=1)
    background: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    traits: tuple[str, ...] = Field(min_length=1)
    values: tuple[str, ...] = Field(default_factory=tuple)
    goal_ids: tuple[str, ...] = Field(default_factory=tuple)
    private_claim_ids: tuple[str, ...] = Field(default_factory=tuple)


class RelationshipSeed(AIModel):
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    values: dict[RelationshipDimensionValue, float] = Field(default_factory=dict)


class GoalSeed(AIModel):
    goal_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: float = Field(ge=0.0, le=1.0)


class TensionSeed(AIModel):
    tension_id: str = Field(min_length=1)
    observer_id: str = Field(min_length=1)
    rival_id: str = Field(min_length=1)
    focus_id: str = Field(min_length=1)
    appraisal: str = Field(min_length=1)


class ThreadSeed(AIModel):
    thread_id: str = Field(min_length=1)
    premise: str = Field(min_length=1)
    participant_ids: tuple[str, ...] = Field(min_length=1)
    stakes: str = Field(min_length=1)


class WorldSeed(VersionedOutput):
    """World-builder draft; persistence requires user confirmation later."""

    expected_schema_version: ClassVar[str] = "world-seed"
    expected_role: ClassVar[AIPromptRole] = AIPromptRole.WORLD_BUILDER
    template_id: str = Field(default="school_romance", min_length=1, max_length=80)
    title: str = Field(min_length=1)
    premise: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    content_boundaries: ContentBoundaryProposal
    locations: tuple[LocationSeed, ...] = Field(min_length=1)
    player_character: CharacterSeed
    npc_profiles: tuple[CharacterSeed, ...] = Field(min_length=2, max_length=4)
    initial_claims: tuple[KnowledgeClaimProposal, ...] = Field(default_factory=tuple)
    initial_relationships: tuple[RelationshipSeed, ...] = Field(default_factory=tuple)
    initial_beliefs: tuple[BeliefProposal, ...] = Field(default_factory=tuple)
    goals: tuple[GoalSeed, ...] = Field(default_factory=tuple)
    tensions: tuple[TensionSeed, ...] = Field(default_factory=tuple)
    threads: tuple[ThreadSeed, ...] = Field(default_factory=tuple)
    opening_scene: SceneSpec


AIOutput = TurnPlan | SimulationResult | ConsistencyReport | NarrativeDraft | CritiqueResult | WorldSeed


__all__ = [
    "AIModel",
    "AIOutput",
    "AIPromptRole",
    "AIProvenance",
    "AddClaimLinkOperation",
    "AddKnowledgeClaimOperation",
    "AddObservationOperation",
    "AdvanceClockOperation",
    "ApplyRelationshipDeltaOperation",
    "AssertCanonFactOperation",
    "Beat",
    "BeliefProposal",
    "ClaimLinkKind",
    "ClaimLinkProposal",
    "ClaimPolarity",
    "ClaimReference",
    "CharacterSeed",
    "ConsistencyReport",
    "ConsistencyStatus",
    "ConsistencyViolation",
    "ConsentTransitionOperation",
    "ConsentStateValue",
    "ContentBoundaryProposal",
    "CritiqueDecision",
    "CritiqueIssue",
    "CritiqueResult",
    "DiagnosticSeverity",
    "EvidenceReference",
    "GoalSeed",
    "KnowledgeClaimProposal",
    "KnowledgeRequirement",
    "LocationSeed",
    "LLMRunTrace",
    "NarrativeDraft",
    "NPCReaction",
    "ObservationProposal",
    "OutcomeCandidate",
    "ParagraphMapping",
    "PlayerMoveSuggestion",
    "ParseStatus",
    "RatingValue",
    "RelationshipDimensionValue",
    "RelationshipSeed",
    "RequiredCheck",
    "RoleInput",
    "SceneSpec",
    "SetCharacterConditionOperation",
    "SetCharacterLocationOperation",
    "SimulationResult",
    "StateOperation",
    "StatePatchProposal",
    "TargetedEvidenceManifest",
    "TokenUsageSnapshot",
    "ThreadAction",
    "ThreadDirective",
    "ThreadSeed",
    "TimeWindow",
    "TransitionThreadOperation",
    "TurnPlan",
    "UncertaintyNote",
    "UpdateBeliefOperation",
    "UpdatePsychologyOperation",
    "ValidationQuery",
    "VersionedOutput",
    "ViolenceCeilingValue",
    "WorldSeed",
]
