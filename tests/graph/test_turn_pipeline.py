from __future__ import annotations

import copy
import json
from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from src.application.contracts.ai import AIPromptRole, SimulationResult, TurnPlan
from src.application.contracts.providers import (
    ConnectivityResult,
    EmbeddingResponse,
    ExecutionMode,
    ProviderCapability,
    ProviderRequest,
    ProviderResponse,
    StreamChunk,
    StructuredResponse,
    StructuredSchema,
)
from src.application.contracts.retrieval import (
    EmbeddingMetadata,
    EmbeddingRecord,
    MemoryCandidate,
    MemoryKind,
    RetrievalScope,
    content_hash,
)
from src.application.ports.providers import ProviderPort
from src.domain.characters import Character, CharacterProfile, CharacterState
from src.domain.content import ContentPolicy
from src.domain.guard import DomainGuard
from src.domain.knowledge import KnowledgeClaim
from src.domain.narrative import NarrativeThread
from src.domain.relationships import RelationshipVector
from src.domain.state import GameState
from src.graph import TurnPipeline, TurnPipelineDependencies, TurnPipelineRequest
from src.graph.checkpoint import build_in_memory_checkpointer
from src.graph.nodes import scene_from_plan
from src.services.ai.contracts import AIContractRegistry
from src.services.retrieval.embeddings import DEFAULT_EMBEDDING_VERSION, InMemoryEmbeddingStore
from src.services.retrieval.tracing import InMemoryRetrievalTraceStore

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ai"
ROLE_OUTPUTS = json.loads((FIXTURE_ROOT / "role_outputs.json").read_text(encoding="utf-8"))


class FakeProvider(ProviderPort):
    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-deterministic"

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset(
            {
                ProviderCapability.STRUCTURED,
                ProviderCapability.TEXT,
                ProviderCapability.STREAM,
                ProviderCapability.EMBEDDING,
            }
        )

    def __init__(self, *, sequences: Mapping[str, Sequence[Mapping[str, Any]]] | None = None) -> None:
        self.sequences = {role: [copy.deepcopy(item) for item in values] for role, values in (sequences or {}).items()}
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.fused_calls: list[tuple[str, ...]] = []
        self.requests: list[ProviderRequest] = []
        self.contracts = AIContractRegistry()

    async def generate_text(self, request: ProviderRequest) -> ProviderResponse:
        return self._response(request, "fake text")

    async def generate_structured(self, request: ProviderRequest, schema: StructuredSchema) -> StructuredResponse:
        role = str(request.role)
        self.requests.append(request)
        self.calls.append((request.physical_call_id, (role,)))
        payload = self._next_payload(role)
        return StructuredResponse(response=self._response(request, json.dumps(payload)), data=payload)

    async def generate_fused_structured(
        self,
        requests: Mapping[Any, ProviderRequest],
        schemas: Mapping[Any, StructuredSchema],
    ) -> Mapping[Any, StructuredResponse]:
        roles = tuple(str(role) for role in requests)
        self.requests.extend(requests.values())
        self.fused_calls.append(roles)
        self.calls.append((next(iter(requests.values())).physical_call_id, roles))
        payloads = {str(role): self._next_payload(str(role)) for role in requests}
        return {
            role: StructuredResponse(
                response=self._response(request, json.dumps(payloads[str(role)])),
                data=payloads[str(role)],
            )
            for role, request in requests.items()
        }

    def _next_payload(self, role: str) -> Mapping[str, Any]:
        values = self.sequences.get(role)
        if values:
            return copy.deepcopy(values.pop(0))
        return copy.deepcopy(ROLE_OUTPUTS[role])

    def _response(self, request: ProviderRequest, text: str) -> ProviderResponse:
        return ProviderResponse(
            provider=self.provider_name,
            model=self.model,
            role=request.role,
            physical_call_id=request.physical_call_id,
            text=text,
            request_id=f"request:{request.physical_call_id}",
            finish_reason="stop",
        )

    def stream_text(self, request: ProviderRequest) -> AsyncIterator[StreamChunk]:
        async def stream() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(
                provider=self.provider_name,
                model=self.model,
                role=request.role,
                physical_call_id=request.physical_call_id,
                text="fake text",
                index=0,
                done=True,
            )

        return stream()

    async def embed(self, texts: Sequence[str], *, model: str | None = None) -> EmbeddingResponse:
        return EmbeddingResponse(provider=self.provider_name, model=model or self.model, embeddings=tuple((1.0,) for _ in texts))

    async def check_connectivity(self) -> ConnectivityResult:
        return ConnectivityResult(provider=self.provider_name, model=self.model, reachable=True, latency_ms=0.0)

    async def aclose(self) -> None:
        return None


class CandidateSource:
    def __init__(self) -> None:
        self.candidates = (
            MemoryCandidate(
                source_id="event-1",
                kind=MemoryKind.CLAIM,
                playthrough_id="playthrough-1",
                branch_id="root",
                world_time=0,
                text="Alice located at library.",
                owner_id="public",
                source_event_id="event-1",
                claim_id="claim-alice-library",
                branch_scope="root",
                entity_ids=("alice", "library"),
                predicate="located_at",
                subject_id="alice",
                object_id="library",
            ),
        )

    async def list_candidates(self, scope: RetrievalScope) -> tuple[MemoryCandidate, ...]:
        return self.candidates


class EmptyCandidateSource:
    async def list_candidates(self, scope: RetrievalScope) -> tuple[MemoryCandidate, ...]:
        del scope
        return ()


class FakeCommitter:
    def __init__(self) -> None:
        self.bundles: list[Any] = []

    async def commit_turn(self, bundle: Any) -> dict[str, Any]:
        self.bundles.append(bundle)
        return {"turn_id": bundle.turn_id, "status": "completed"}


def make_game_state() -> GameState:
    state = GameState.empty(
        world_id="world-1",
        playthrough_id="playthrough-1",
        branch_id="root",
        policy=ContentPolicy(),
    )
    state.locations = {"library", "courtyard"}
    state.characters = {
        "player": Character(
            CharacterProfile(
                "player",
                "Mina",
                17,
                role="new club member",
                background="Mina transferred schools and hopes the club will offer a fresh start.",
                voice="curious and direct",
            ),
            CharacterState(),
        ),
        "alice": Character(
            CharacterProfile(
                "alice",
                "Alice",
                17,
                role="club president",
                background="Alice inherited responsibility for an underfunded festival exhibition.",
                voice="warm but precise",
                traits=("diligent", "reserved"),
                initial_secrets=("secret-alice-letter",),
            ),
            CharacterState(),
        ),
    }
    return state


def make_request(state: GameState, run_id: str = "turn-run-1") -> TurnPipelineRequest:
    return TurnPipelineRequest(
        turn_run_id=run_id,
        playthrough_id=state.playthrough_id,
        branch_id=state.branch_id,
        base_revision=0,
        raw_input="Offer to help Alice with the festival display.",
        actor_id="player",
        game_state=state,
    )


def test_scene_uses_planned_content_classification_and_persisted_world_tone() -> None:
    contracts = AIContractRegistry()
    plan = contracts.parse(AIPromptRole.PLANNER, ROLE_OUTPUTS["planner"])
    simulation = contracts.parse(AIPromptRole.SIMULATOR, ROLE_OUTPUTS["simulator"])
    assert isinstance(plan, TurnPlan)
    assert isinstance(simulation, SimulationResult)
    state = make_game_state()
    state.metadata["world_profile"] = {"tone": "intimate, ominous"}

    scene = scene_from_plan(
        {"turn_run_id": "turn-run-1", "actor_id": "player"},  # type: ignore[arg-type]
        state,
        plan,
        simulation,
    )

    assert scene.tags == ("romantic_affection",)
    assert scene.violence_detail.value == "none"
    assert scene.tone == "intimate, ominous"


def make_pipeline(
    provider: FakeProvider,
    committer: FakeCommitter,
    *,
    mode: str = "quality",
    cancellation: Any = None,
    derived_job_handler: Any = None,
    failure_hook: Any = None,
    candidate_source: Any = None,
    embedding_store: Any = None,
    retrieval_trace_store: Any = None,
) -> TurnPipeline:
    dependencies = TurnPipelineDependencies(
        provider=provider,
        committer=committer,
        candidate_source=CandidateSource() if candidate_source is None else candidate_source,
        embedding_store=embedding_store,
        retrieval_trace_store=retrieval_trace_store,
        guard=DomainGuard(),
        cancellation=cancellation,
        execution_mode=ExecutionMode(mode),
        derived_job_handler=derived_job_handler,
    )
    pipeline = TurnPipeline(dependencies, checkpointer=build_in_memory_checkpointer())
    # The public runner intentionally keeps crash injection in the runtime
    # only for the resume acceptance test.
    if failure_hook is not None:
        pipeline.dependencies.event_sink = None
    return pipeline


@pytest.mark.asyncio
async def test_fake_pipeline_commits_one_canonical_turn() -> None:
    provider = FakeProvider()
    committer = FakeCommitter()
    pipeline = make_pipeline(provider, committer)

    result = await pipeline.run(make_request(make_game_state()))

    assert result["status"] == "completed"
    assert result["commit_done"] is True
    assert result["derived_jobs_queued"] is True
    assert len(committer.bundles) == 1
    assert committer.bundles[0].claims[0].claim_id == "claim-alice-library"
    assert committer.bundles[0].duration_minutes == 5
    assert committer.bundles[0].world_time_end == 5
    assert [item["kind"] for item in committer.bundles[0].suggested_actions] == ["act", "speak", "observe", "think"]
    assert any(item["event_type"] == "completed" for item in result["node_events"])


@pytest.mark.asyncio
async def test_pipeline_commits_json_rng_state_without_treating_it_as_a_mapping() -> None:
    state = make_game_state()
    state.metadata["rng_seed"] = "stable-seed"
    state.metadata["rng_state"] = {}
    committer = FakeCommitter()

    result = await make_pipeline(FakeProvider(), committer).run(make_request(state, "rng-state-run"))

    assert result["status"] == "completed"
    assert len(committer.bundles) == 1
    rng_state = committer.bundles[0].rng_state
    assert isinstance(rng_state, list)
    assert isinstance(rng_state[0], int)


@pytest.mark.asyncio
async def test_pipeline_uses_stored_embeddings_and_records_retrieval_trace() -> None:
    provider = FakeProvider()
    candidate_source = CandidateSource()
    candidate = candidate_source.candidates[0]
    store = InMemoryEmbeddingStore()
    await store.save(
        EmbeddingRecord(
            metadata=EmbeddingMetadata(
                source_id=candidate.source_id,
                source_kind=candidate.kind,
                playthrough_id=candidate.playthrough_id,
                branch_id=candidate.branch_id,
                model=provider.model,
                dimensions=1,
                embedding_version=DEFAULT_EMBEDDING_VERSION,
                content_hash=content_hash(candidate.text),
            ),
            vector=(1.0,),
        )
    )
    traces = InMemoryRetrievalTraceStore()
    pipeline = make_pipeline(
        provider,
        FakeCommitter(),
        candidate_source=candidate_source,
        embedding_store=store,
        retrieval_trace_store=traces,
    )

    result = await pipeline.run(make_request(make_game_state(), "hybrid-run"))

    assert result["status"] == "completed"
    assert result.get("context_manifest", {}).get("embedding_model") == provider.model
    saved_traces = await traces.list()
    assert saved_traces
    assert saved_traces[0].embedding_enabled is True
    assert saved_traces[0].hits[0].embedding_score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_fast_fused_planner_simulator_matches_quality_artifacts() -> None:
    quality_provider = FakeProvider()
    quality_committer = FakeCommitter()
    quality = await make_pipeline(quality_provider, quality_committer).run(make_request(make_game_state(), "quality-run"))

    fast_provider = FakeProvider()
    fast_committer = FakeCommitter()
    fast = make_pipeline(fast_provider, fast_committer, mode="fast")
    fast_result = await fast.run(make_request(make_game_state(), "fast-run"))

    assert quality["status"] == fast_result["status"] == "completed"
    assert quality.get("final_narrative") == fast_result.get("final_narrative")
    assert quality.get("approved_patch") == fast_result.get("approved_patch")
    assert not any(item["fused"] for item in quality["physical_call_traces"])
    assert any(
        item["fused"] and set(item["logical_roles"]) == {"planner", "simulator"} for item in fast_result["physical_call_traces"]
    )


@pytest.mark.asyncio
async def test_guard_rejection_repairs_once_before_commit() -> None:
    invalid = copy.deepcopy(ROLE_OUTPUTS["simulator"])
    invalid["state_patch"]["operations"][0]["location_id"] = "unknown-location"
    provider = FakeProvider(sequences={"simulator": (invalid, ROLE_OUTPUTS["simulator"])})
    committer = FakeCommitter()

    result = await make_pipeline(provider, committer).run(make_request(make_game_state()))

    assert result["status"] == "completed"
    assert result["retry_counters"]["repair"] == 1
    assert len(committer.bundles) == 1


@pytest.mark.asyncio
async def test_invalid_model_mutations_after_repair_are_dropped_without_blocking_turn() -> None:
    invalid = copy.deepcopy(ROLE_OUTPUTS["simulator"])
    invalid["claim_proposals"][0]["subject_id"] = "colorful-posters"
    provider = FakeProvider(sequences={"simulator": (invalid, invalid)})
    committer = FakeCommitter()

    result = await make_pipeline(provider, committer).run(make_request(make_game_state(), "guard-fallback-run"))

    assert result["status"] == "completed"
    assert result["commit_done"] is True
    assert result["retry_counters"]["repair"] == 1
    assert result["warnings"][-1]["code"] == "invalid_model_mutations_dropped"
    assert any(event["event_type"] == "guard_fallback" for event in result["node_events"])
    assert len(committer.bundles) == 1
    assert committer.bundles[0].approved_patch["operations"] == [
        {"operation_type": "advance_clock", "payload": {"duration_minutes": 1}}
    ]
    assert committer.bundles[0].duration_minutes == 1
    assert any(roles == ("writer",) for _, roles in provider.calls)


@pytest.mark.asyncio
async def test_simulator_without_canonical_mutations_gets_default_clock_progress() -> None:
    simulation = copy.deepcopy(ROLE_OUTPUTS["simulator"])
    simulation["claim_proposals"] = []
    simulation["state_patch"] = None
    simulation["knowledge_requirements"] = []
    committer = FakeCommitter()

    result = await make_pipeline(
        FakeProvider(sequences={"simulator": (simulation,)}),
        committer,
    ).run(make_request(make_game_state(), "mutation-free-run"))

    assert result["status"] == "completed"
    assert result["retry_counters"].get("repair", 0) == 0
    assert committer.bundles[0].approved_patch["operations"] == [
        {"operation_type": "advance_clock", "payload": {"duration_minutes": 1}}
    ]
    assert committer.bundles[0].world_time_end == 1


@pytest.mark.asyncio
async def test_initial_context_exposes_exact_authoritative_ids() -> None:
    result = await make_pipeline(FakeProvider(), FakeCommitter()).run(make_request(make_game_state(), "ids-run"))

    context_manifest = result.get("context_manifest")
    assert isinstance(context_manifest, dict)
    identifiers = context_manifest["authoritative_ids"]
    assert identifiers["character_ids"] == ["alice", "player"]
    assert identifiers["location_ids"] == ["courtyard", "library"]
    assert identifiers["event_ids"] == []


@pytest.mark.asyncio
async def test_initial_context_carries_the_canonical_story_language_to_every_role() -> None:
    provider = FakeProvider()
    state = make_game_state()
    state.metadata["world_profile"] = {"story_language": "vi", "tone": "ấm áp"}

    result = await make_pipeline(provider, FakeCommitter()).run(make_request(state, "language-run"))

    context_manifest = result.get("context_manifest")
    assert isinstance(context_manifest, dict)
    assert context_manifest["story_language"] == "vi"
    assert context_manifest["world_profile"]["story_language"] == "vi"
    assert provider.requests
    assert all('"story_language":"vi"' in request.user_prompt for request in provider.requests)


@pytest.mark.asyncio
async def test_initial_context_includes_bounded_public_character_backgrounds() -> None:
    provider = FakeProvider()
    state = make_game_state()
    state.claims["secret-alice-letter"] = KnowledgeClaim(
        "alice",
        "secret_exists",
        object_id="alice-letter",
        branch_scope="alice",
        claim_id="secret-alice-letter",
    )
    result = await make_pipeline(provider, FakeCommitter()).run(make_request(state, "character-profile-run"))

    context_manifest = result.get("context_manifest")
    assert isinstance(context_manifest, dict)
    profiles = context_manifest["character_profiles"]
    assert profiles["player"]["background"] == "Mina transferred schools and hopes the club will offer a fresh start."
    assert profiles["alice"] == {
        "character_id": "alice",
        "name": "Alice",
        "aliases": [],
        "age": 17,
        "gender": "unspecified",
        "role": "club president",
        "background": "Alice inherited responsibility for an underfunded festival exhibition.",
        "voice": "warm but precise",
        "traits": ["diligent", "reserved"],
        "values": [],
        "boundaries": [],
        "goal_ids": [],
        "goals": [],
    }
    assert "initial_secrets" not in profiles["alice"]
    assert "private_character_context" not in context_manifest
    assert context_manifest["authoritative_ids"]["secret_ids"] == []
    assert "secret-alice-letter" not in context_manifest["authoritative_ids"]["claim_ids"]

    planner_request = next(request for request in provider.requests if request.role == AIPromptRole.PLANNER)
    simulator_request = next(request for request in provider.requests if request.role == AIPromptRole.SIMULATOR)
    validator_request = next(request for request in provider.requests if request.role == AIPromptRole.CONTEXT_VALIDATOR)
    writer_request = next(request for request in provider.requests if request.role == AIPromptRole.WRITER)
    critic_request = next(request for request in provider.requests if request.role == AIPromptRole.CRITIC)
    assert "Alice inherited responsibility" in planner_request.user_prompt
    assert "Alice inherited responsibility" in simulator_request.user_prompt
    assert "Alice inherited responsibility" in writer_request.user_prompt
    assert "secret-alice-letter" not in planner_request.user_prompt
    assert "secret-alice-letter" in simulator_request.user_prompt
    assert "secret-alice-letter" in validator_request.user_prompt
    assert "secret-alice-letter" not in writer_request.user_prompt
    assert "secret-alice-letter" not in critic_request.user_prompt
    assert '"character_relationships"' not in writer_request.user_prompt
    assert '"emotional_tensions"' not in writer_request.user_prompt
    assert '"character_relationships"' not in critic_request.user_prompt
    assert '"emotional_tensions"' not in critic_request.user_prompt


@pytest.mark.asyncio
async def test_fast_mode_keeps_private_npc_context_inside_simulation_roles() -> None:
    provider = FakeProvider()
    state = make_game_state()
    state.claims["secret-alice-letter"] = KnowledgeClaim(
        "alice",
        "secret_exists",
        object_id="alice-letter",
        branch_scope="alice",
        claim_id="secret-alice-letter",
    )

    await make_pipeline(provider, FakeCommitter(), mode="fast").run(make_request(state, "fast-private-context-run"))

    prompts = {request.role: request.user_prompt for request in provider.requests}
    assert "secret-alice-letter" not in prompts[AIPromptRole.PLANNER]
    assert "secret-alice-letter" in prompts[AIPromptRole.SIMULATOR]
    assert "secret-alice-letter" in prompts[AIPromptRole.CONTEXT_VALIDATOR]
    assert "secret-alice-letter" not in prompts[AIPromptRole.WRITER]
    assert "secret-alice-letter" not in prompts[AIPromptRole.CRITIC]


@pytest.mark.asyncio
async def test_initial_context_connects_background_to_goals_relationships_tensions_and_threads() -> None:
    state = make_game_state()
    for character_id, character in tuple(state.characters.items()):
        state.characters[character_id] = Character(character.profile, CharacterState(location_id="library"))
    state.characters["bob"] = Character(
        CharacterProfile(
            "bob",
            "Bob",
            18,
            role="club artist",
            background="Bob wants the exhibition to preserve the club's identity.",
        ),
        CharacterState(location_id="library"),
    )
    state.metadata["character_goals"] = {
        "alice": [
            {
                "goal_id": "goal-alice-save-club",
                "owner_id": "alice",
                "description": "Save the club through a successful exhibition.",
                "priority": 0.9,
            }
        ]
    }
    state.metadata["emotional_tensions"] = [
        {
            "tension_id": "tension-alice-bob-player",
            "observer_id": "alice",
            "rival_id": "bob",
            "focus_id": "player",
            "appraisal": "Alice worries Bob will gain the player's trust first.",
        }
    ]
    state.relationships[("alice", "bob")] = RelationshipVector.from_mapping({"trust": 0.3, "respect": 0.4})
    state.threads["thread-save-club"] = NarrativeThread(
        "thread-save-club",
        "The exhibition may determine whether the club survives.",
        "root",
        participant_ids=("player", "alice", "bob"),
        stakes="Failure could dissolve the club.",
        urgency=0.7,
    )

    result = await make_pipeline(FakeProvider(), FakeCommitter()).run(make_request(state, "structured-background-run"))

    context_manifest = result.get("context_manifest")
    assert isinstance(context_manifest, dict)
    assert context_manifest["character_profiles"]["alice"]["goals"][0]["goal_id"] == "goal-alice-save-club"
    assert context_manifest["character_relationships"] == [
        {"source_id": "alice", "target_id": "bob", "values": {"respect": 0.4, "trust": 0.3}}
    ]
    assert context_manifest["emotional_tensions"][0]["tension_id"] == "tension-alice-bob-player"
    assert context_manifest["story_threads"][0]["thread_id"] == "thread-save-club"


@pytest.mark.asyncio
async def test_new_claim_and_idempotent_location_do_not_require_prior_exact_claim() -> None:
    simulation = copy.deepcopy(ROLE_OUTPUTS["simulator"])
    simulation["claim_proposals"][0].update(
        {
            "proposal_id": "claim-alice-festival-goal",
            "predicate": "goal_active",
            "object_id": "festival-planning",
        }
    )
    simulation["knowledge_requirements"] = []
    state = make_game_state()
    state.characters["alice"] = state.characters["alice"].with_state(location_id="library")
    provider = FakeProvider(sequences={"simulator": (simulation,)})
    committer = FakeCommitter()

    result = await make_pipeline(
        provider,
        committer,
        candidate_source=EmptyCandidateSource(),
    ).run(make_request(state, "new-claim-run"))

    assert result["status"] == "completed"
    assert result.get("targeted_evidence") == ()
    assert len(committer.bundles) == 1
    assert committer.bundles[0].claims[0].claim_id == "claim-alice-festival-goal"


@pytest.mark.asyncio
async def test_missing_explicit_evidence_is_reported_as_a_turn_error() -> None:
    result = await make_pipeline(
        FakeProvider(),
        FakeCommitter(),
        candidate_source=EmptyCandidateSource(),
    ).run(make_request(make_game_state(), "missing-evidence-run"))

    assert result["status"] == "failed"
    assert any(error["code"] == "insufficient_evidence" for error in result["errors"])


@pytest.mark.asyncio
async def test_planner_contract_error_retries_with_same_role_contract() -> None:
    invalid = copy.deepcopy(ROLE_OUTPUTS["planner"])
    invalid.pop("candidate_beats")
    provider = FakeProvider(sequences={"planner": (invalid, ROLE_OUTPUTS["planner"])})
    committer = FakeCommitter()

    result = await make_pipeline(provider, committer).run(make_request(make_game_state()))

    assert result["status"] == "completed"
    planner_traces = [trace for trace in result["llm_traces"] if trace["logical_role"] == "planner"]
    assert planner_traces
    assert planner_traces[0]["retry_count"] == 1


@pytest.mark.asyncio
async def test_cancellation_before_commit_leaves_canonical_boundary_untouched() -> None:
    from src.application.contracts.providers import CancellationToken

    token = CancellationToken()
    token.cancel()
    committer = FakeCommitter()
    state = make_game_state()
    result = await make_pipeline(FakeProvider(), committer, cancellation=token).run(make_request(state))

    assert result["status"] == "cancelled"
    assert result["commit_done"] is False
    assert committer.bundles == []
    assert state.characters["alice"].state.location_id is None


@pytest.mark.asyncio
async def test_derived_job_failure_preserves_completed_canonical_turn() -> None:
    async def fail_derived(_: tuple[dict[str, Any], ...], __: Any) -> None:
        raise RuntimeError("derived worker unavailable")

    committer = FakeCommitter()
    result = await make_pipeline(
        FakeProvider(),
        committer,
        derived_job_handler=fail_derived,
    ).run(make_request(make_game_state()))

    assert result["status"] == "completed"
    assert result["commit_done"] is True
    assert result["derived_jobs_queued"] is False
    assert len(committer.bundles) == 1
    assert any(error["code"] == "derived_job_failure" for error in result["errors"])


@pytest.mark.asyncio
async def test_checkpoint_resume_does_not_double_commit_after_one_crash() -> None:
    provider = FakeProvider()
    committer = FakeCommitter()
    crashed = False

    def crash_once(node: str) -> None:
        nonlocal crashed
        if node == "build_canonical_records" and not crashed:
            crashed = True
            raise RuntimeError("simulated process crash")

    from src.graph.builder import build_turn_graph
    from src.graph.checkpoint import checkpoint_config
    from src.graph.runtime import TurnGraphRuntime
    from src.graph.state import initial_graph_state

    state = make_game_state()
    request = make_request(state, "resume-run")
    runtime = TurnGraphRuntime(
        request=request,
        provider=provider,
        candidate_source=CandidateSource(),
        committer=committer,
        guard=DomainGuard(),
        failure_hook=crash_once,
    )
    graph = build_turn_graph(runtime, checkpointer=build_in_memory_checkpointer())
    initial = initial_graph_state(
        turn_run_id=request.turn_run_id,
        playthrough_id=request.playthrough_id,
        branch_id=request.branch_id,
        base_revision=request.base_revision,
        raw_input=request.raw_input,
        actor_id=request.actor_id,
    )

    with pytest.raises(RuntimeError, match="simulated process crash"):
        await graph.ainvoke(initial, config=checkpoint_config(request.turn_run_id))
    result = await graph.ainvoke(None, config=checkpoint_config(request.turn_run_id))

    assert result["status"] == "completed"
    assert len(committer.bundles) == 1
