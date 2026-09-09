from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.application.contracts.ai import (
    AIPromptRole,
    RoleInput,
    StatePatchProposal,
    TargetedEvidenceManifest,
    ValidationQuery,
)
from src.application.contracts.providers import ProviderResponse, TokenUsage
from src.services.ai.contracts import AIContractRegistry, AIContractValidationError
from src.services.ai.tracing import build_llm_run_trace
from src.services.prompts import PromptRegistry

FIXTURES = Path(__file__).parents[1] / "fixtures" / "ai" / "role_outputs.json"
SUPPORTING_FIXTURES = Path(__file__).parents[1] / "fixtures" / "ai" / "supporting_contracts.json"


def _fixtures() -> dict[str, Any]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def _supporting_fixtures() -> dict[str, Any]:
    return json.loads(SUPPORTING_FIXTURES.read_text(encoding="utf-8"))


@pytest.mark.parametrize("role", tuple(AIPromptRole))
def test_fake_provider_fixture_parses_into_versioned_role_contract(role: AIPromptRole) -> None:
    registry = AIContractRegistry()
    result = registry.parse(role, _fixtures()[role.value])

    assert result.role == role
    assert result.run_id == ("world-run-1" if role == AIPromptRole.WORLD_BUILDER else "turn-run-1")
    assert result.schema_version == registry.model_for(role).expected_schema_version


def test_schema_error_has_field_diagnostic() -> None:
    payload = {
        "schema_version": "turn-plan",
        "role": "planner",
        "run_id": "turn-run-1",
        "prompt_version": "1.0.0",
        "interpreted_player_intent": "help",
        "candidate_beats": [],
    }

    with pytest.raises(AIContractValidationError) as error_info:
        AIContractRegistry().parse(AIPromptRole.PLANNER, payload)

    diagnostic_paths = {item.path for item in error_info.value.diagnostics}
    assert "candidate_beats" in diagnostic_paths
    assert "possible_outcomes" in diagnostic_paths
    assert "planner contract validation failed" in str(error_info.value)


def test_invalid_json_has_safe_diagnostic() -> None:
    with pytest.raises(AIContractValidationError) as error_info:
        AIContractRegistry().parse_json(AIPromptRole.WRITER, "not-json-with-secret")

    assert error_info.value.diagnostics[0].code == "invalid_json"
    assert "not-json-with-secret" not in str(error_info.value)


def test_unregistered_predicate_is_rejected_before_authority() -> None:
    payload = copy.deepcopy(_fixtures()["simulator"])
    claim = payload["claim_proposals"][0]
    claim["predicate"] = "invented_canon_fact"

    with pytest.raises(AIContractValidationError) as error_info:
        AIContractRegistry().parse(AIPromptRole.SIMULATOR, payload)

    assert any("predicate" in item.path or "predicate" in item.message for item in error_info.value.diagnostics)


def test_state_patch_rejects_untyped_operation() -> None:
    payload = copy.deepcopy(_fixtures()["simulator"]["state_patch"])
    payload["operations"] = [{"operation_type": "free_form_mutation", "value": "change canon"}]

    with pytest.raises(ValidationError) as error_info:
        StatePatchProposal.model_validate(payload)

    assert "operation_type" in str(error_info.value)


def test_world_seed_rejects_unknown_opening_scene_character() -> None:
    payload = copy.deepcopy(_fixtures()["world_builder"])
    payload["opening_scene"]["participants"]["unknown"] = 17

    with pytest.raises(AIContractValidationError) as error_info:
        AIContractRegistry().parse(AIPromptRole.WORLD_BUILDER, payload)

    assert error_info.value.diagnostics[0].code == "unknown_character_reference"


def test_structured_schema_returns_typed_model() -> None:
    registry = AIContractRegistry()
    schema = registry.structured_schema(AIPromptRole.PLANNER)
    result = schema.validate(_fixtures()["planner"], provider="fixture")

    assert result.__class__.__name__ == "TurnPlan"
    assert result.role == AIPromptRole.PLANNER


@pytest.mark.parametrize("role", tuple(AIPromptRole))
def test_provider_schema_pins_each_role_schema_version(role: AIPromptRole) -> None:
    registry = AIContractRegistry()
    schema = registry.structured_schema(role).json_schema

    schema_version = schema["properties"]["schema_version"]
    assert schema_version["enum"] == [registry.model_for(role).expected_schema_version]
    assert "const" not in schema_version


@pytest.mark.parametrize("role", tuple(AIPromptRole))
def test_role_model_rejects_wrong_schema_version(role: AIPromptRole) -> None:
    payload = copy.deepcopy(_fixtures()[role.value])
    payload["schema_version"] = f"{payload['schema_version']}-v1"

    with pytest.raises(ValidationError, match="expected schema version"):
        AIContractRegistry().model_for(role).model_validate(payload)


def test_registered_claim_predicates_are_exposed_in_provider_json_schema() -> None:
    schema = AIContractRegistry().structured_schema(AIPromptRole.WORLD_BUILDER).json_schema

    predicate = schema["$defs"]["KnowledgeClaimProposal"]["properties"]["predicate"]

    assert predicate["enum"] == [
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


def test_world_seed_schema_normalizes_one_provider_envelope_with_authoritative_trace_metadata() -> None:
    payload = copy.deepcopy(_fixtures()["world_builder"])
    world_seed = {
        key: value
        for key, value in payload.items()
        if key not in {"schema_version", "role", "run_id", "prompt_version", "physical_call_id"}
    }
    wrapped = {
        "schema_version": "world-seed",
        "role": "world_builder",
        "run_id": "provider-invented-run",
        "metadata": {"prompt": "not contract metadata"},
        "world_seed": world_seed,
    }
    schema = AIContractRegistry().structured_schema(
        AIPromptRole.WORLD_BUILDER,
        authoritative_metadata={
            "schema_version": "world-seed",
            "role": "world_builder",
            "run_id": "authoritative-run",
            "prompt_version": "1.0.1",
            "physical_call_id": "authoritative-call",
        },
    )

    result = schema.validate(wrapped, provider="fixture")

    assert result.__class__.__name__ == "WorldSeed"
    assert result.title == payload["title"]
    assert result.run_id == "authoritative-run"
    assert result.prompt_version == "1.0.1"
    assert result.physical_call_id == "authoritative-call"


def test_role_envelope_with_unknown_outer_fields_remains_invalid() -> None:
    payload = copy.deepcopy(_fixtures()["world_builder"])
    wrapped = {"world_seed": payload, "unexpected_authority": True}

    with pytest.raises(AIContractValidationError):
        AIContractRegistry().parse(AIPromptRole.WORLD_BUILDER, wrapped)


def test_supporting_validation_and_evidence_contracts_parse() -> None:
    fixtures = _supporting_fixtures()
    query = ValidationQuery.model_validate(fixtures["validation_query"])
    manifest = TargetedEvidenceManifest.model_validate(fixtures["targeted_evidence_manifest"])

    assert query.requirement_id == "req-alice-location"
    assert manifest.evidence[0].claim_id == "claim-alice-library"


def test_empty_evidence_manifest_must_report_insufficient_evidence() -> None:
    payload = _supporting_fixtures()["targeted_evidence_manifest"]
    payload["evidence"] = []

    with pytest.raises(ValidationError, match="insufficient_evidence"):
        TargetedEvidenceManifest.model_validate(payload)


def test_role_input_is_versioned_and_strict() -> None:
    role_input = RoleInput(
        input_schema_version="role-input",
        role=AIPromptRole.WRITER,
        run_id="turn-run-1",
        context_manifest_id="manifest-1",
        branch_id="root",
        world_time=3,
        context={"scene": "approved"},
    )

    assert role_input.input_schema_version == "role-input"
    with pytest.raises(ValidationError):
        RoleInput.model_validate({**role_input.model_dump(), "unexpected": True})


def test_llm_run_trace_records_prompt_and_schema_versions_without_raw_output() -> None:
    response = ProviderResponse(
        provider="ollama",
        model="fixture-model",
        role=AIPromptRole.WRITER,
        physical_call_id="call-write-1",
        text="raw narrative that must not enter the trace",
        request_id="request-1",
        usage=TokenUsage(prompt_tokens=4, completion_tokens=8, total_tokens=12),
        latency_ms=12.5,
        retry_count=1,
        fallback_from="primary",
    )

    prompt = PromptRegistry().get(AIPromptRole.WRITER)
    trace = build_llm_run_trace(
        response,
        run_id="turn-run-1",
        role=AIPromptRole.WRITER,
        prompt=prompt,
        config_snapshot_id="config-1",
        parse_status="repaired",
    )

    assert trace.prompt_version == prompt.semantic_version
    assert trace.output_schema_version == "narrative-draft"
    assert trace.token_usage is not None
    assert trace.token_usage.total_tokens == 12
    assert trace.raw_output_stored is False
    assert "raw narrative" not in trace.model_dump_json()
