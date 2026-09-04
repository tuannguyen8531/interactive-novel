"""Bounded turn graph nodes and typed AI-to-domain conversion."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar, cast

from src.application.contracts.ai import (
    AddClaimLinkOperation,
    AddKnowledgeClaimOperation,
    AddObservationOperation,
    AdvanceClockOperation,
    AIPromptRole,
    AIProvenance,
    ApplyRelationshipDeltaOperation,
    AssertCanonFactOperation,
    ClaimReference,
    ConsistencyReport,
    ConsistencyStatus,
    ConsistencyViolation,
    CritiqueDecision,
    CritiqueResult,
    DiagnosticSeverity,
    KnowledgeClaimProposal,
    NarrativeDraft,
    SetCharacterConditionOperation,
    SetCharacterLocationOperation,
    SimulationResult,
    TransitionThreadOperation,
    TurnPlan,
    UpdateBeliefOperation,
    UpdatePsychologyOperation,
)
from src.application.contracts.ai import (
    SceneSpec as AISceneSpec,
)
from src.application.contracts.providers import (
    ExecutionMode,
    ProviderCancelledError,
)
from src.application.contracts.retrieval import InitialContextRequest, RetrievalScope
from src.domain.content import ConsentState, Rating, ViolenceCeiling
from src.domain.content import SceneSpec as DomainSceneSpec
from src.domain.errors import GuardRejected
from src.domain.events import Belief, Observation
from src.domain.knowledge import ClaimLink, ClaimLinkKind, KnowledgeClaim
from src.domain.language import StoryLanguage
from src.domain.narrative import ThreadStatus
from src.domain.patch import (
    AddClaimLink,
    AddKnowledgeClaim,
    AddObservation,
    AdvanceClock,
    ApplyRelationshipDelta,
    AssertCanonFact,
    ConsentTransition,
    SetCharacterCondition,
    SetCharacterLocation,
    StatePatch,
    TransitionThread,
    UpdateBelief,
    UpdatePsychology,
)
from src.domain.values import Provenance, TimeRange
from src.services.llm.safety import normalize_player_input, untrusted_player_context
from src.services.logger import log_error
from src.services.retrieval.claims import ClaimExtractor
from src.services.retrieval.context import ContextAssembler
from src.services.retrieval.embeddings import OllamaEmbeddingIndexer

from .events import NodeEvent, publish_event
from .execution import RoleExecutionResult, RoleExecutor
from .records import build_canonical_bundle
from .runtime import TurnGraphRuntime
from .state import TurnGraphState

_T = TypeVar("_T")
_MAX_CONTEXT_CHARACTERS = 4
_MAX_CONTEXT_BACKGROUND_CHARS = 2_000


class TurnGraphNodes:
    """Node implementation with runtime dependencies captured outside state."""

    def __init__(self, runtime: TurnGraphRuntime) -> None:
        self.runtime = runtime
        embedding_indexer = (
            OllamaEmbeddingIndexer(
                runtime.embedding_store,
                embedding_version=runtime.embedding_version,
                enabled=True,
            )
            if runtime.embedding_store is not None
            else None
        )
        self.assembler = ContextAssembler(
            embedding_indexer=embedding_indexer,
            embedding_store=runtime.embedding_store,
            trace_store=runtime.retrieval_trace_store,
        )
        self.extractor = ClaimExtractor()

    async def normalize_input(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("normalize_input", state, self._normalize_input)

    async def build_initial_context(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("build_initial_context", state, self._build_initial_context)

    async def plan(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("plan", state, self._plan)

    async def simulate(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("simulate", state, self._simulate)

    async def extract_claims(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("extract_claims", state, self._extract_claims)

    async def retrieve_targeted_evidence(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("retrieve_targeted_evidence", state, self._retrieve_targeted_evidence)

    async def validate_context(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("validate_context", state, self._validate_context)

    async def guard_state(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("guard_state", state, self._guard_state)

    async def repair(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("repair", state, self._repair)

    async def write(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("write", state, self._write)

    async def critique(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("critique", state, self._critique)

    async def revise(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("revise", state, self._revise)

    async def build_canonical_records(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("build_canonical_records", state, self._build_canonical_records)

    async def commit(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("commit", state, self._commit)

    async def enqueue_derived_jobs(self, state: TurnGraphState) -> dict[str, Any]:
        return await self._guarded("enqueue_derived_jobs", state, self._enqueue_derived_jobs)

    async def _guarded(
        self,
        node: str,
        state: TurnGraphState,
        body: Callable[[TurnGraphState], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        working = dict(state)
        event_prefix = _EVENT_PREFIXES.get(node, node)
        working["node_events"] = await self._event(working, node, f"{event_prefix}_started")
        # A one-shot failure hook is intentionally outside the error boundary:
        # it models a process crash between checkpointed nodes.
        if self.runtime.failure_hook is not None:
            self.runtime.failure_hook(node)
        try:
            self._check_cancelled()
            update = await body(cast(TurnGraphState, working))
            merged = {**working, **update}
            if node == "write" and merged.get("final_narrative"):
                merged["node_events"] = await self._event(
                    merged,
                    node,
                    "writer_token",
                    {"text": str(merged["final_narrative"]), "index": 0, "done": False},
                )
            merged["node_events"] = await self._event(merged, node, f"{event_prefix}_completed")
            return merged
        except ProviderCancelledError:
            return await self._cancelled(cast(TurnGraphState, working), node)
        except Exception as error:
            log_error(
                "Turn graph node failed",
                error,
                node=node,
                turn_run_id=working.get("turn_run_id"),
                playthrough_id=working.get("playthrough_id"),
                branch_id=working.get("branch_id"),
            )
            errors = _append_error(working, node, type(error).__name__, str(error))
            failed = {"status": "failed", "errors": errors}
            merged = {**working, **failed}
            merged["node_events"] = await self._event(merged, node, "failed", {"error_type": type(error).__name__})
            return merged

    async def _normalize_input(self, state: TurnGraphState) -> dict[str, Any]:
        decision = normalize_player_input(state["raw_input"], max_chars=self.runtime.input_max_chars)
        if not decision.accepted:
            return _failure(state, "invalid_input", "Turn input cannot be blank.")
        return {"normalized_input": decision.normalized, "input_safety": decision.as_dict()}

    async def _build_initial_context(self, state: TurnGraphState) -> dict[str, Any]:
        if state.get("context_manifest") is not None:
            return {}
        game_state = self.runtime.request.game_state
        scope = RetrievalScope(
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
            branch_ancestry=game_state.branch_ancestry,
            world_time=game_state.world_time,
            owner_id=state.get("actor_id"),
        )
        query_entity_ids = _query_entity_ids(state, game_state)
        relevant_character_ids = _relevant_character_ids(game_state, query_entity_ids)
        request = InitialContextRequest(
            run_id=state["turn_run_id"],
            role=AIPromptRole.PLANNER.value,
            scope=scope,
            query_text=state.get("normalized_input", state["raw_input"]),
            entity_ids=tuple(dict.fromkeys((*query_entity_ids, *relevant_character_ids))),
            token_budget=2_000,
            max_items=40,
            recent_event_limit=8,
        )
        if self.runtime.candidate_source is None:
            manifest = await self.assembler.build_initial_context(request, [], provider=self.runtime.provider)
        else:
            manifest = await self.assembler.build_initial_context_from_source(
                request,
                self.runtime.candidate_source,
                provider=self.runtime.provider,
            )
        context_manifest = manifest.as_context()
        context_manifest["authoritative_ids"] = _authoritative_ids(game_state, owner_id=state.get("actor_id"))
        context_manifest["world_profile"] = dict(game_state.metadata.get("world_profile", {}))
        context_manifest["story_language"] = _story_language(game_state).value
        context_manifest["world_profile"]["story_language"] = _story_language(game_state).value
        context_manifest["character_profiles"] = _public_character_profiles(game_state, relevant_character_ids)
        context_manifest["story_threads"] = _relevant_story_threads(game_state, relevant_character_ids)
        context_manifest["character_relationships"] = _relevant_relationships(game_state, relevant_character_ids)
        context_manifest["emotional_tensions"] = _relevant_tensions(game_state, relevant_character_ids)
        if game_state.policy is not None:
            context_manifest["content_policy"] = {
                "rating": game_state.policy.rating.value,
                "adult_explicit_permitted": game_state.policy.rating == Rating.ADULT_18_PLUS,
                "violence_ceiling": game_state.policy.violence_ceiling.value,
                "consent": {
                    "required": game_state.policy.consent.required,
                    "explicit_affirmative": game_state.policy.consent.explicit_affirmative,
                    "withdrawal_supported": game_state.policy.consent.withdrawal_supported,
                },
            }
        return {"context_manifest": context_manifest}

    async def _plan(self, state: TurnGraphState) -> dict[str, Any]:
        if state.get("plan") is not None and not state.get("repair_requested", False):
            return {}
        context = _role_context(state)
        roles: tuple[AIPromptRole, ...]
        if self.runtime.execution_mode == ExecutionMode.FAST:
            roles = (AIPromptRole.PLANNER, AIPromptRole.SIMULATOR)
        else:
            roles = (AIPromptRole.PLANNER,)
        contexts = {role: context for role in roles}
        if AIPromptRole.SIMULATOR in roles:
            contexts[AIPromptRole.SIMULATOR] = _with_private_character_context(
                context,
                self.runtime.request.game_state,
                actor_id=state.get("actor_id"),
            )
        result = await self._execute(roles, state, contexts, call_prefix="plan")
        plan = cast(TurnPlan, result.artifacts[AIPromptRole.PLANNER])
        update: dict[str, Any] = {"plan": plan, **_trace_update(state, result)}
        if AIPromptRole.SIMULATOR in result.artifacts:
            update["simulation"] = result.artifacts[AIPromptRole.SIMULATOR]
        return update

    async def _simulate(self, state: TurnGraphState) -> dict[str, Any]:
        if state.get("simulation") is not None and not state.get("repair_requested", False):
            return {}
        plan = state.get("plan")
        if not isinstance(plan, TurnPlan):
            return _failure(state, "plan_missing", "Simulator requires a planner artifact.")
        context = _role_context(
            state,
            plan=plan.model_dump(mode="json"),
            repair_feedback=state.get("repair_feedback"),
        )
        context = _with_private_character_context(
            context,
            self.runtime.request.game_state,
            actor_id=state.get("actor_id"),
        )
        result = await self._execute(
            (AIPromptRole.SIMULATOR,),
            state,
            {AIPromptRole.SIMULATOR: context},
            repair_attempt=state.get("retry_counters", {}).get("repair", 0),
            call_prefix="simulate",
        )
        return {
            "simulation": result.artifacts[AIPromptRole.SIMULATOR],
            "repair_requested": False,
            "guard_error": None,
            **_trace_update(state, result),
        }

    async def _extract_claims(self, state: TurnGraphState) -> dict[str, Any]:
        simulation = state.get("simulation")
        plan = state.get("plan")
        if not isinstance(simulation, SimulationResult):
            return _failure(state, "simulation_missing", "Claim extraction requires a simulation artifact.")
        extraction = self.extractor.extract(
            simulation,
            plan=plan if isinstance(plan, TurnPlan) else None,
            actor_id=state.get("actor_id"),
            include_implicit_claim_requirements=False,
            current_locations={
                character_id: character.state.location_id
                for character_id, character in self.runtime.request.game_state.characters.items()
            },
        )
        return {"claim_extraction": extraction}

    async def _retrieve_targeted_evidence(self, state: TurnGraphState) -> dict[str, Any]:
        extraction = state.get("claim_extraction")
        if extraction is None:
            return _failure(state, "claim_extraction_missing", "Targeted retrieval requires extracted claims.")
        game_state = self.runtime.request.game_state
        manifests: list[dict[str, Any]] = []
        requirements = {item.requirement_id: item for item in extraction.knowledge_requirements}
        if self.runtime.candidate_source is None:
            candidates: list[Any] = []
        else:
            base_scope = RetrievalScope(
                playthrough_id=state["playthrough_id"],
                branch_id=state["branch_id"],
                branch_ancestry=game_state.branch_ancestry,
                world_time=game_state.world_time,
                owner_id=state.get("actor_id"),
            )
            candidates = list(await self.runtime.candidate_source.list_candidates(base_scope))
        for query in extraction.validation_queries:
            scope = RetrievalScope(
                playthrough_id=state["playthrough_id"],
                branch_id=state["branch_id"],
                branch_ancestry=game_state.branch_ancestry,
                world_time=query.world_time,
                owner_id=query.actor_id,
            )
            requirement = requirements.get(query.requirement_id)
            manifest = await self.assembler.targeted_evidence(
                query,
                candidates,
                scope=scope,
                requirement=requirement,
                run_id=state["turn_run_id"],
                provider=self.runtime.provider,
            )
            manifests.append(manifest.model_dump(mode="json"))
        return {"targeted_evidence": tuple(manifests)}

    async def _validate_context(self, state: TurnGraphState) -> dict[str, Any]:
        report = state.get("consistency_report")
        if isinstance(report, ConsistencyReport) and not state.get("repair_requested", False):
            return {}
        manifests = tuple(state.get("targeted_evidence", ()))
        insufficient = [item for item in manifests if bool(item.get("insufficient_evidence"))]
        if insufficient:
            violation = ConsistencyViolation(
                violation_id=f"insufficient-evidence:{insufficient[0].get('query_id', 'unknown')}",
                code="insufficient_evidence",
                severity=DiagnosticSeverity.ERROR,
                description="Targeted retrieval did not find authorized evidence for a required check.",
            )
            prompt = self._executor().prompts.get(AIPromptRole.CONTEXT_VALIDATOR)
            report = ConsistencyReport(
                schema_version="consistency-report",
                role=AIPromptRole.CONTEXT_VALIDATOR,
                run_id=state["turn_run_id"],
                prompt_version=prompt.semantic_version,
                physical_call_id=f"deterministic-validator-{state['turn_run_id']}",
                status=ConsistencyStatus.INSUFFICIENT_EVIDENCE,
                violations=(violation,),
                evidence_manifest_ids=tuple(item.get("retrieval_trace_id", "") for item in manifests),
                recommended_corrections=("Retrieve authorized evidence or revise the proposed claim.",),
            )
            final_failure = state.get("retry_counters", {}).get("repair", 0) >= self.runtime.max_repair_attempts
            update: dict[str, Any] = {
                "consistency_report": report,
                "status": "failed" if final_failure else "running",
            }
            if final_failure:
                message = violation.description
                update["errors"] = _append_error(state, "validate_context", violation.code, message)
                log_error(
                    "Turn consistency validation failed",
                    message,
                    code=violation.code,
                    turn_run_id=state["turn_run_id"],
                    playthrough_id=state["playthrough_id"],
                    branch_id=state["branch_id"],
                    evidence_manifest_ids=list(report.evidence_manifest_ids),
                )
            return update

        plan = state.get("plan")
        simulation = state.get("simulation")
        extraction = state.get("claim_extraction")
        context = _role_context(
            state,
            targeted_evidence=list(manifests),
            plan=plan.model_dump(mode="json") if isinstance(plan, TurnPlan) else None,
            simulation=simulation.model_dump(mode="json") if isinstance(simulation, SimulationResult) else None,
            claim_extraction=_claim_extraction_context(extraction),
        )
        context = _with_private_character_context(
            context,
            self.runtime.request.game_state,
            actor_id=state.get("actor_id"),
        )
        result = await self._execute(
            (AIPromptRole.CONTEXT_VALIDATOR,),
            state,
            {AIPromptRole.CONTEXT_VALIDATOR: context},
            call_prefix="validate",
        )
        report = cast(ConsistencyReport, result.artifacts[AIPromptRole.CONTEXT_VALIDATOR])
        final_failure = (
            report.status != ConsistencyStatus.PASS
            and state.get("retry_counters", {}).get("repair", 0) >= self.runtime.max_repair_attempts
        )
        update = {
            "consistency_report": report,
            "status": "failed" if final_failure else "running",
            **_trace_update(state, result),
        }
        if final_failure:
            message = "; ".join(item.description for item in report.violations) or report.status.value
            update["errors"] = _append_error(state, "validate_context", report.status.value, message)
            log_error(
                "Turn consistency validation failed",
                message,
                code=report.status.value,
                turn_run_id=state["turn_run_id"],
                playthrough_id=state["playthrough_id"],
                branch_id=state["branch_id"],
                evidence_manifest_ids=list(report.evidence_manifest_ids),
            )
        return update

    async def _guard_state(self, state: TurnGraphState) -> dict[str, Any]:
        report = state.get("consistency_report")
        if not isinstance(report, ConsistencyReport):
            return _failure(state, "consistency_report_missing", "Guard requires a context consistency report.")
        if report.status != ConsistencyStatus.PASS:
            return {
                "guard_approved": False,
                "guard_error": {
                    "code": "context_not_approved",
                    "message": report.status.value,
                },
            }
        simulation = state.get("simulation")
        if not isinstance(simulation, SimulationResult):
            return _failure(state, "simulation_missing", "Guard requires a simulation artifact.")
        try:
            patch = domain_patch_from_simulation(simulation, branch_id=state["branch_id"])
            patch = _ensure_turn_clock(
                patch,
                current_world_time=self.runtime.request.game_state.world_time,
                default_duration_minutes=self.runtime.guard.clock_policy.default_action_duration_minutes,
            )
            self.runtime.guard.validate_patch(self.runtime.request.game_state, patch)
        except GuardRejected as error:
            diagnostic = {"code": error.code, "message": error.message, "details": dict(error.details)}
            return await self._handle_patch_rejection(state, simulation, diagnostic)
        except (TypeError, ValueError) as error:
            diagnostic = {"code": "invalid_typed_patch", "message": str(error), "details": {}}
            return await self._handle_patch_rejection(state, simulation, diagnostic)
        from src.domain.codec import patch_to_payload

        return {
            "guard_approved": True,
            "guard_error": None,
            "approved_patch": patch_to_payload(patch),
        }

    async def _handle_patch_rejection(
        self,
        state: TurnGraphState,
        simulation: SimulationResult,
        diagnostic: dict[str, Any],
    ) -> dict[str, Any]:
        repair_count = state.get("retry_counters", {}).get("repair", 0)
        final_attempt = repair_count >= self.runtime.max_repair_attempts
        recovery = "drop_invalid_mutations" if final_attempt else "repair"
        log_error(
            "Turn state Guard rejected a model proposal",
            str(diagnostic["message"]),
            code=diagnostic["code"],
            details=diagnostic.get("details", {}),
            recovery=recovery,
            repair_attempt=repair_count,
            turn_run_id=state["turn_run_id"],
            playthrough_id=state["playthrough_id"],
            branch_id=state["branch_id"],
        )
        if not final_attempt:
            return {
                "guard_approved": False,
                "guard_error": diagnostic,
                "approved_patch": None,
                "status": "running",
            }

        # Model-proposed mutations are optional. After the bounded repair has
        # also failed, reject them but keep the deterministic clock fallback,
        # usable NPC reaction and outcome so the player is not locked out.
        from src.domain.codec import patch_to_payload

        game_state = self.runtime.request.game_state
        fallback_duration = self.runtime.guard.clock_policy.default_action_duration_minutes
        safe_patch = StatePatch.from_operations(
            (AdvanceClock(fallback_duration),) if fallback_duration > 0 else (),
            branch_id=state["branch_id"],
            base_world_time=game_state.world_time,
            patch_id=f"guard-fallback:{state['turn_run_id']}",
        )
        self.runtime.guard.validate_patch(game_state, safe_patch)
        warning = {
            "node": "guard_state",
            "code": "invalid_model_mutations_dropped",
            "message": "The model proposed invalid canonical mutations; the turn continued without applying them.",
            "guard_error": diagnostic,
        }
        events = await self._event(state, "guard_state", "guard_fallback", warning)
        return {
            "guard_approved": True,
            "guard_error": None,
            "approved_patch": patch_to_payload(safe_patch),
            "simulation": simulation.model_copy(
                update={
                    "claim_proposals": (),
                    "state_patch": None,
                    "knowledge_requirements": (),
                }
            ),
            "claim_extraction": None,
            "targeted_evidence": (),
            "warnings": (*tuple(state.get("warnings", ())), warning),
            "node_events": events,
            "status": "running",
        }

    async def _repair(self, state: TurnGraphState) -> dict[str, Any]:
        counters = dict(state.get("retry_counters", {}))
        attempt = counters.get("repair", 0)
        if attempt >= self.runtime.max_repair_attempts:
            return _failure(state, "repair_limit_exceeded", "Guard/context repair limit was reached.")
        counters["repair"] = attempt + 1
        report = state.get("consistency_report")
        feedback: dict[str, Any] = {}
        if isinstance(report, ConsistencyReport):
            feedback["consistency_report"] = report.model_dump(mode="json")
        if state.get("guard_error") is not None:
            feedback["guard_error"] = dict(state["guard_error"] or {})
        return {
            "retry_counters": counters,
            "repair_requested": True,
            "repair_feedback": feedback,
            "simulation": None,
            "claim_extraction": None,
            "targeted_evidence": (),
            "consistency_report": None,
            "approved_patch": None,
            "guard_approved": False,
            "guard_error": None,
        }

    async def _write(self, state: TurnGraphState) -> dict[str, Any]:
        if state.get("draft") is not None:
            return {}
        plan = state.get("plan")
        simulation = state.get("simulation")
        if not isinstance(plan, TurnPlan) or not isinstance(simulation, SimulationResult):
            return _failure(state, "writer_input_missing", "Writer requires plan and simulation artifacts.")
        scene = scene_from_plan(state, self.runtime.request.game_state, plan, simulation)
        self.runtime.guard.validate_scene(self.runtime.request.game_state, domain_scene_from_ai(scene))
        scene = scene.model_copy(update={"guard_approved": True})
        context = _role_context(
            state,
            plan=plan.model_dump(mode="json"),
            simulation=simulation.model_dump(mode="json"),
            scene_spec=scene.model_dump(mode="json"),
        )
        context.pop("character_relationships", None)
        context.pop("emotional_tensions", None)
        context.pop("private_character_context", None)
        result = await self._execute(
            (AIPromptRole.WRITER,),
            state,
            {AIPromptRole.WRITER: context},
            repair_attempt=state.get("revision_count", 0),
            call_prefix="write",
        )
        draft = cast(NarrativeDraft, result.artifacts[AIPromptRole.WRITER])
        return {
            "scene_spec": scene,
            "draft": draft,
            "final_narrative": draft.narrative_text,
            **_trace_update(state, result),
        }

    async def _critique(self, state: TurnGraphState) -> dict[str, Any]:
        if state.get("critique") is not None:
            return {}
        draft = state.get("draft")
        scene = state.get("scene_spec")
        if not isinstance(draft, NarrativeDraft) or not isinstance(scene, AISceneSpec):
            return _failure(state, "critique_input_missing", "Critic requires a scene spec and narrative draft.")
        context = _role_context(
            state,
            scene_spec=scene.model_dump(mode="json"),
            draft=draft.model_dump(mode="json"),
        )
        context.pop("character_relationships", None)
        context.pop("emotional_tensions", None)
        context.pop("private_character_context", None)
        result = await self._execute(
            (AIPromptRole.CRITIC,),
            state,
            {AIPromptRole.CRITIC: context},
            call_prefix="critique",
        )
        critique = cast(CritiqueResult, result.artifacts[AIPromptRole.CRITIC])
        exhausted = critique.decision == CritiqueDecision.REJECT or (
            critique.decision == CritiqueDecision.REVISE and state.get("revision_count", 0) >= self.runtime.max_revision_attempts
        )
        return {
            "critique": critique,
            "status": "failed" if exhausted else "running",
            **_trace_update(state, result),
        }

    async def _revise(self, state: TurnGraphState) -> dict[str, Any]:
        critique = state.get("critique")
        if not isinstance(critique, CritiqueResult):
            return _failure(state, "critique_missing", "Revision requires a critique artifact.")
        count = state.get("revision_count", 0)
        if count >= self.runtime.max_revision_attempts:
            return _failure(state, "revision_limit_exceeded", "Writer/critic revision limit was reached.")
        return {
            "revision_count": count + 1,
            "draft": None,
            "final_narrative": None,
            "critique": None,
        }

    async def _build_canonical_records(self, state: TurnGraphState) -> dict[str, Any]:
        if state.get("canonical_bundle") is not None:
            return {}
        bundle = build_canonical_bundle(state, self.runtime.request.game_state)
        intents = tuple(
            {
                "job_type": job_type,
                "playthrough_id": bundle.playthrough_id,
                "branch_id": bundle.branch_id,
                "source_turn_id": bundle.turn_id,
                "source_revision": bundle.base_revision + 1,
            }
            for job_type in bundle.derived_job_types
        )
        return {"canonical_bundle": bundle, "derived_job_intents": intents}

    async def _commit(self, state: TurnGraphState) -> dict[str, Any]:
        if state.get("commit_done", False):
            return {}
        self._check_cancelled()
        bundle = state.get("canonical_bundle")
        if bundle is None:
            return _failure(state, "canonical_bundle_missing", "Commit requires canonical records.")
        result = await self.runtime.committer.commit_turn(bundle)
        return {"committed_turn": result, "commit_done": True, "status": "committed"}

    async def _enqueue_derived_jobs(self, state: TurnGraphState) -> dict[str, Any]:
        if state.get("derived_jobs_queued", False):
            return {"status": "completed"}
        if not state.get("commit_done", False):
            return _failure(state, "commit_missing", "Derived jobs require a completed canonical commit.")
        bundle = state.get("canonical_bundle")
        intents = tuple(state.get("derived_job_intents", ()))
        if self.runtime.derived_job_handler is not None:
            try:
                await self.runtime.derived_job_handler(intents, cast(Any, bundle))
            except Exception as error:
                # Canonical completion is intentionally preserved.  Derived
                # artifacts are retryable and must not turn a completed turn
                # back into a failed canonical turn.
                errors = _append_error(state, "enqueue_derived_jobs", "derived_job_failure", str(error))
                events = await self._event(state, "enqueue_derived_jobs", "completed")
                return {"status": "completed", "derived_jobs_queued": False, "errors": errors, "node_events": events}
        events = await self._event(state, "enqueue_derived_jobs", "completed")
        return {"status": "completed", "derived_jobs_queued": True, "node_events": events}

    async def _execute(
        self,
        roles: tuple[AIPromptRole, ...],
        state: TurnGraphState,
        contexts: Mapping[AIPromptRole, Mapping[str, Any]],
        *,
        repair_attempt: int = 0,
        call_prefix: str,
    ) -> RoleExecutionResult:
        return await self._executor().execute(
            roles,
            run_id=state["turn_run_id"],
            branch_id=state["branch_id"],
            world_time=self.runtime.request.game_state.world_time,
            contexts=cast(Mapping[Any, Mapping[str, Any]], contexts),
            cancellation=self.runtime.cancellation,
            repair_attempt=repair_attempt,
            call_prefix=f"{state['turn_run_id']}-{call_prefix}",
        )

    def _executor(self) -> RoleExecutor:
        config_id = self.runtime.request.config_snapshot_id
        provider_object: Any = self.runtime.provider
        snapshot_method = provider_object.config_snapshot if hasattr(provider_object, "config_snapshot") else None
        if snapshot_method is not None:
            snapshot = snapshot_method()
            config_id = str(snapshot.get("schema_version", config_id))
        return RoleExecutor(
            self.runtime.provider,
            execution_mode=self.runtime.execution_mode,
            config_snapshot_id=config_id,
            max_contract_retries=self.runtime.max_contract_retries,
            telemetry=self.runtime.telemetry,
        )

    async def _event(
        self,
        state: Mapping[str, Any],
        node: str,
        event_type: str,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], ...]:
        sequence = len(tuple(state.get("node_events", ()))) + 1
        event = NodeEvent(
            event_type=event_type,
            node=node,
            turn_run_id=str(state["turn_run_id"]),
            sequence=sequence,
            payload=dict(payload or {}),
        )
        await publish_event(self.runtime.event_sink, event)
        return (*tuple(state.get("node_events", ())), event.as_dict())

    async def _cancelled(self, state: TurnGraphState, node: str) -> dict[str, Any]:
        return {
            "status": "cancelled",
            "cancellation_requested": True,
            "node_events": await self._event(state, node, "cancelled"),
        }

    def _check_cancelled(self) -> None:
        if self.runtime.cancellation is not None:
            self.runtime.cancellation.raise_if_cancelled()


def _role_context(state: TurnGraphState, **extra: Any) -> dict[str, Any]:
    context = dict(state.get("context_manifest", {}))
    world_profile = context.get("world_profile")
    configured_language = context.get("story_language")
    if configured_language is None and isinstance(world_profile, Mapping):
        configured_language = world_profile.get("story_language")
    try:
        context["story_language"] = StoryLanguage(str(configured_language or StoryLanguage.ENGLISH.value)).value
    except ValueError:
        context["story_language"] = StoryLanguage.ENGLISH.value
    normalized_input = str(state.get("normalized_input", state["raw_input"]))
    safety = state.get("input_safety", {})
    context["normalized_input"] = normalized_input
    context["player_input"] = untrusted_player_context(normalize_player_input(normalized_input))
    context["input_safety"] = dict(safety)
    context["targeted_evidence"] = list(state.get("targeted_evidence", ()))
    context.update(extra)
    return context


def _story_language(game_state: Any) -> StoryLanguage:
    """Read the canonical world language with a safe legacy fallback."""

    metadata = getattr(game_state, "metadata", {})
    world_profile = metadata.get("world_profile", {}) if isinstance(metadata, Mapping) else {}
    candidate = world_profile.get("story_language") if isinstance(world_profile, Mapping) else None
    if candidate is None and isinstance(metadata, Mapping):
        candidate = metadata.get("story_language")
    try:
        return StoryLanguage(str(candidate or StoryLanguage.ENGLISH.value))
    except ValueError:
        return StoryLanguage.ENGLISH


def _claim_extraction_context(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "proposed_claims": [item.model_dump(mode="json") for item in value.proposed_claims],
        "proposed_mutations": [item.model_dump(mode="json") for item in value.proposed_mutations],
        "knowledge_requirements": [item.model_dump(mode="json") for item in value.knowledge_requirements],
        "validation_queries": [item.model_dump(mode="json") for item in value.validation_queries],
        "claim_to_mutation": {key: list(items) for key, items in value.claim_to_mutation.items()},
    }


_EVENT_PREFIXES = {
    "normalize_input": "input",
    "build_initial_context": "context",
    "plan": "planner",
    "simulate": "simulator",
    "extract_claims": "claims_extracted",
    "retrieve_targeted_evidence": "targeted_retrieval",
    "validate_context": "validator",
    "guard_state": "guard",
    "repair": "repair",
    "write": "writer",
    "critique": "critic",
    "revise": "revision",
    "build_canonical_records": "canonical_records",
    "commit": "commit",
    "enqueue_derived_jobs": "derived_jobs",
}


def _trace_update(state: TurnGraphState, result: RoleExecutionResult) -> dict[str, Any]:
    return {
        "llm_traces": tuple(state.get("llm_traces", ())) + tuple(trace.model_dump(mode="json") for trace in result.llm_traces),
        "physical_call_traces": tuple(state.get("physical_call_traces", ())) + result.physical_call_traces,
    }


def _append_error(state: Mapping[str, Any], node: str, code: str, message: str) -> tuple[dict[str, Any], ...]:
    errors = tuple(state.get("errors", ()))
    return (*errors, {"node": node, "code": code, "message": message})


def _failure(state: TurnGraphState, code: str, message: str) -> dict[str, Any]:
    return {"status": "failed", "errors": _append_error(state, "pipeline", code, message)}


def _query_entity_ids(state: TurnGraphState, game_state: Any) -> tuple[str, ...]:
    """Boost only the actor and entities actually mentioned in this move."""

    query_text = str(state.get("normalized_input", state["raw_input"])).casefold()
    identifiers: list[str] = []

    def add(identifier: str) -> None:
        if identifier and identifier not in identifiers:
            identifiers.append(identifier)

    add(str(state.get("actor_id", "")))
    for character_id, character in game_state.characters.items():
        names = (character_id, character.profile.display_name, *character.profile.aliases)
        if any(_mentions_entity(query_text, name) for name in names):
            add(character_id)
    for location_id in game_state.locations:
        if _mentions_entity(query_text, location_id):
            add(location_id)
    return tuple(identifiers)


def _mentions_entity(query_text: str, name: str) -> bool:
    normalized = name.strip().casefold()
    return bool(normalized and re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", query_text))


def _relevant_character_ids(game_state: Any, entity_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Select the actor, mentioned characters and nearby participants within a small bound."""

    relevant = [entity_id for entity_id in entity_ids if entity_id in game_state.characters]
    actor_id = relevant[0] if relevant else None
    actor = game_state.characters.get(actor_id) if actor_id is not None else None
    actor_location = actor.state.location_id if actor is not None else None
    if actor_location is not None:
        relevant.extend(
            character_id
            for character_id, character in sorted(game_state.characters.items())
            if character.state.location_id == actor_location
        )
    return tuple(dict.fromkeys(relevant))[:_MAX_CONTEXT_CHARACTERS]


def _public_character_profiles(game_state: Any, character_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """Expose bounded stable public characterization without private secrets."""

    profiles: dict[str, dict[str, Any]] = {}
    all_goals = game_state.metadata.get("character_goals", {})
    goals_by_character = all_goals if isinstance(all_goals, Mapping) else {}
    for character_id in character_ids:
        character = game_state.characters.get(character_id)
        if character is None:
            continue
        profile = character.profile
        background = profile.background.strip()
        if len(background) > _MAX_CONTEXT_BACKGROUND_CHARS:
            background = f"{background[: _MAX_CONTEXT_BACKGROUND_CHARS - 1].rstrip()}…"
        profiles[character_id] = {
            "character_id": character_id,
            "name": profile.display_name,
            "aliases": list(profile.aliases),
            "age": profile.age_at(game_state.world_time),
            "gender": profile.gender,
            "role": profile.role,
            "background": background,
            "voice": profile.voice,
            "traits": list(profile.traits),
            "values": list(profile.values),
            "boundaries": list(profile.boundaries),
            "goal_ids": list(profile.long_term_goals),
            "goals": list(goals_by_character.get(character_id, ())),
        }
    return profiles


def _with_private_character_context(
    context: Mapping[str, Any],
    game_state: Any,
    *,
    actor_id: str | None,
) -> dict[str, Any]:
    """Give simulation roles owner-scoped NPC canon without exposing it to prose roles."""

    result = dict(context)
    profiles = context.get("character_profiles", {})
    character_ids = tuple(profiles) if isinstance(profiles, Mapping) else ()
    private_context: dict[str, dict[str, Any]] = {}
    for character_id in character_ids:
        if character_id == actor_id:
            continue
        claims = [
            {
                "claim_id": claim.claim_id,
                "predicate": claim.predicate,
                "object_id": claim.object_id,
                "typed_value": claim.typed_value,
                "polarity": claim.polarity,
                "qualifiers": dict(claim.qualifiers),
                "valid_time": {"start": claim.valid_time.start, "end": claim.valid_time.end},
            }
            for _, claim in sorted(game_state.claims.items())
            if claim.branch_scope == character_id and claim.valid_time.contains(game_state.world_time)
        ]
        if claims:
            private_context[character_id] = {"owner_id": character_id, "claims": claims}
    if private_context:
        result["private_character_context"] = private_context
    else:
        result.pop("private_character_context", None)
    return result


def _relevant_story_threads(game_state: Any, character_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    relevant = set(character_ids)
    return [
        {
            "thread_id": thread.thread_id,
            "premise": thread.premise,
            "participant_ids": list(thread.participant_ids),
            "stakes": thread.stakes,
            "status": thread.status.value,
            "progress": thread.progress,
            "urgency": thread.urgency,
        }
        for _, thread in sorted(game_state.threads.items())
        if not thread.participant_ids or relevant.intersection(thread.participant_ids)
    ][:8]


def _relevant_relationships(game_state: Any, character_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    relevant = set(character_ids)
    relationships = []
    for (source_id, target_id), vector in sorted(game_state.relationships.items()):
        if source_id not in relevant or target_id not in relevant:
            continue
        values = {dimension: value for dimension, value in vector.values.items() if abs(value) > 1e-9}
        relationships.append({"source_id": source_id, "target_id": target_id, "values": values})
    return relationships


def _relevant_tensions(game_state: Any, character_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    relevant = set(character_ids)
    raw_tensions = game_state.metadata.get("emotional_tensions", ())
    if not isinstance(raw_tensions, (tuple, list)):
        return []
    return [
        dict(item)
        for item in raw_tensions
        if isinstance(item, Mapping)
        and {str(item.get("observer_id")), str(item.get("rival_id")), str(item.get("focus_id"))}.issubset(relevant)
    ][:8]


def _authoritative_ids(game_state: Any, *, owner_id: str | None = None) -> dict[str, list[str]]:
    """Expose only exact, Guard-authorized identifiers to logical AI roles."""

    goal_ids: set[str] = set()
    item_ids: set[str] = set()
    secret_ids: set[str] = set()
    for character_id, character in game_state.characters.items():
        goal_ids.update(character.profile.long_term_goals)
        goal_ids.update(character.state.short_term_goals)
        goal_ids.update(character.state.psychology.active_goals)
        item_ids.update(character.state.inventory_ids)
        if character_id == owner_id:
            secret_ids.update(character.profile.initial_secrets)
    visible_claim_ids = [
        claim_id
        for claim_id, claim in game_state.claims.items()
        if claim.branch_scope in {"public", *game_state.branch_ancestry} or claim.branch_scope == owner_id
    ]
    return {
        "character_ids": sorted(game_state.characters),
        "location_ids": sorted(game_state.locations),
        "event_ids": sorted(game_state.events),
        "claim_ids": sorted(visible_claim_ids),
        "goal_ids": sorted(goal_ids),
        "item_ids": sorted(item_ids),
        "secret_ids": sorted(secret_ids),
        "thread_ids": sorted(game_state.threads),
    }


def domain_patch_from_simulation(simulation: SimulationResult, *, branch_id: str) -> StatePatch:
    """Convert only typed AI operations/claims into domain operations."""

    proposal = simulation.state_patch
    if proposal is None:
        return StatePatch.from_operations(
            (),
            branch_id=branch_id,
            patch_id=f"no-op:{simulation.run_id}",
        )
    if proposal.branch_id != branch_id:
        raise ValueError("simulation patch branch does not match the turn branch")
    operations = [_domain_operation(operation, proposal.provenance) for operation in proposal.operations]
    existing_claim_ids = {operation.claim.claim_id for operation in operations if isinstance(operation, AddKnowledgeClaim)}
    claim_operations = [
        AddKnowledgeClaim(_domain_claim(claim))
        for claim in simulation.claim_proposals
        if claim.proposal_id not in existing_claim_ids
    ]
    return StatePatch.from_operations(
        (*claim_operations, *operations),
        branch_id=branch_id,
        base_world_time=proposal.base_world_time,
        patch_id=proposal.patch_id,
    )


def _ensure_turn_clock(
    patch: StatePatch,
    *,
    current_world_time: int,
    default_duration_minutes: int,
) -> StatePatch:
    """Give completed player turns a deterministic minimum duration.

    The Simulator may estimate a more suitable duration. If it omits clock
    movement (or proposes only zero-minute movement), the application boundary
    adds the configured fallback so an accepted action cannot freeze time.
    """

    elapsed = sum(operation.duration_minutes for operation in patch.operations if isinstance(operation, AdvanceClock))
    if elapsed > 0 or default_duration_minutes <= 0:
        return patch
    return StatePatch.from_operations(
        (*patch.operations, AdvanceClock(default_duration_minutes)),
        branch_id=patch.branch_id,
        base_world_time=patch.base_world_time if patch.base_world_time is not None else current_world_time,
        patch_id=patch.patch_id,
    )


def _domain_provenance(provenance: AIProvenance) -> Provenance:
    return Provenance(
        source_type=provenance.source_type,
        source_id=provenance.source_id,
        run_id=provenance.run_id,
        prompt_version=provenance.prompt_version,
        model_metadata=provenance.model_metadata,
    )


def _domain_claim(proposal: KnowledgeClaimProposal) -> KnowledgeClaim:
    return KnowledgeClaim(
        claim_id=proposal.proposal_id,
        subject_id=proposal.subject_id,
        predicate=proposal.predicate,
        object_id=proposal.object_id,
        typed_value=proposal.typed_value,
        polarity=proposal.polarity.value,
        qualifiers=proposal.qualifiers,
        valid_time=TimeRange(proposal.valid_time.start, proposal.valid_time.end),
        branch_scope=proposal.branch_scope,
        schema_version=proposal.schema_version,
        claim_type=proposal.claim_type,
        provenance=_domain_provenance(proposal.provenance),
    )


def _domain_operation(operation: Any, provenance: AIProvenance) -> Any:
    if isinstance(operation, AdvanceClockOperation):
        return AdvanceClock(operation.duration_minutes)
    if isinstance(operation, SetCharacterLocationOperation):
        return SetCharacterLocation(operation.character_id, operation.location_id)
    if isinstance(operation, SetCharacterConditionOperation):
        return SetCharacterCondition(operation.character_id, operation.condition)
    if isinstance(operation, UpdatePsychologyOperation):
        return UpdatePsychology(operation.character_id, dict(operation.deltas))
    if isinstance(operation, ApplyRelationshipDeltaOperation):
        return ApplyRelationshipDelta(
            source_id=operation.source_id,
            target_id=operation.target_id,
            dimension=operation.dimension.value,
            proposed_delta=operation.proposed_delta,
            cause_event_id=operation.cause_event_id,
            reason=operation.reason,
            provenance=_domain_provenance(provenance),
        )
    if isinstance(operation, AddKnowledgeClaimOperation):
        return AddKnowledgeClaim(_domain_claim(operation.claim))
    if isinstance(operation, AddClaimLinkOperation):
        return AddClaimLink(
            ClaimLink(
                from_claim_id=operation.link.from_claim_id,
                to_claim_id=operation.link.to_claim_id,
                kind=ClaimLinkKind(operation.link.kind.value),
            )
        )
    if isinstance(operation, AssertCanonFactOperation):
        return AssertCanonFact(
            claim_id=operation.claim_id,
            source_event_or_rule=operation.source_event_or_rule,
        )
    if isinstance(operation, AddObservationOperation):
        item = operation.observation
        return AddObservation(
            Observation(
                observation_id=item.observation_id,
                observer_id=item.observer_id,
                observed_claim_id=item.observed_claim_id,
                source_event_id=item.source_event_id,
                method=item.method,
                branch_scope=item.branch_scope,
                world_time=item.world_time,
                confidence=item.confidence,
                distortion=item.distortion,
                provenance=_domain_provenance(provenance),
            )
        )
    if isinstance(operation, UpdateBeliefOperation):
        item = operation.belief
        return UpdateBelief(
            Belief(
                belief_id=item.belief_id,
                believer_id=item.believer_id,
                claim_id=item.claim_id,
                stance=item.stance,
                confidence=item.confidence,
                evidence_ids=item.evidence_ids,
                counter_evidence_ids=item.counter_evidence_ids,
                branch_scope=item.branch_scope,
                world_time=item.world_time,
                source_reliability=item.source_reliability,
                provenance=_domain_provenance(provenance),
            )
        )
    if isinstance(operation, TransitionThreadOperation):
        return TransitionThread(operation.thread_id, ThreadStatus(operation.status), operation.progress_delta)
    from src.application.contracts.ai import ConsentTransitionOperation

    if isinstance(operation, ConsentTransitionOperation):
        return ConsentTransition(
            operation.scene_id,
            operation.participant_id,
            operation.activity_tag,
            ConsentState(operation.next_state.value),
        )
    raise TypeError(f"Unsupported typed state operation: {type(operation).__name__}")


def scene_from_plan(
    state: TurnGraphState,
    game_state: Any,
    plan: TurnPlan,
    simulation: SimulationResult,
) -> AISceneSpec:
    participant_ids = tuple(dict.fromkeys((*plan.characters_involved, *(item.character_id for item in simulation.npc_reactions))))
    participants = {
        character_id: game_state.characters[character_id].profile.age_at(game_state.world_time)
        for character_id in participant_ids
        if character_id in game_state.characters
    }
    if not participants:
        participants = {state.get("actor_id", "player"): 17}
    beats = tuple(item.description for item in plan.candidate_beats)
    visible_actions = beats or (simulation.proposed_outcome,)
    claims = tuple(ClaimReference(claim_id=item.proposal_id) for item in simulation.claim_proposals)
    world_profile = game_state.metadata.get("world_profile", {})
    tone = world_profile.get("tone", "gentle") if isinstance(world_profile, Mapping) else "gentle"
    return AISceneSpec(
        scene_id=f"scene-{state['turn_run_id']}",
        source_role=AIPromptRole.PLANNER,
        source_run_id=state["turn_run_id"],
        guard_approved=False,
        world_time=game_state.world_time,
        tags=plan.content_tags,
        participants=participants,
        consent={},
        violence_detail=plan.violence_detail,
        approved_beats=beats or (simulation.proposed_outcome,),
        visible_actions=visible_actions,
        allowed_dialogue_intents=tuple(plan.intended_focus),
        pov="second_person",
        tone=str(tone or "gentle"),
        continuity_details=tuple(plan.pacing_note for _ in (0,)),
        allowed_claims=claims,
        forbidden_claims=(),
        length_target=300,
    )


def domain_scene_from_ai(scene: AISceneSpec) -> DomainSceneSpec:
    return DomainSceneSpec(
        scene_id=scene.scene_id,
        world_time=scene.world_time,
        tags=scene.tags,
        participants=scene.participants,
        consent={key: ConsentState(value.value) for key, value in scene.consent.items()},
        violence_detail=ViolenceCeiling(scene.violence_detail.value),
    )


__all__ = [
    "TurnGraphNodes",
    "domain_patch_from_simulation",
    "domain_scene_from_ai",
    "scene_from_plan",
]
