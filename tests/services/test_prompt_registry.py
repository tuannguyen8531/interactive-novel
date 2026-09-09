from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.application.contracts.ai import AIPromptRole, RoleInput, WorldSeed
from src.services.ai.contracts import AIContractRegistry, AIContractValidationError
from src.services.prompts import PromptRegistry, PromptRegistryError, prompt_cache_scope


def test_prompt_render_replaces_required_input_without_unresolved_placeholders() -> None:
    registry = PromptRegistry()
    rendered = registry.render(AIPromptRole.PLANNER, input_json='{"run_id":"turn-run-1"}')

    assert "turn-run-1" in rendered
    assert "{{" not in rendered
    assert "Return only JSON" in rendered


def test_render_input_requires_matching_versioned_role() -> None:
    role_input = RoleInput(
        input_schema_version="role-input",
        role=AIPromptRole.WRITER,
        run_id="turn-run-1",
        context_manifest_id="manifest-1",
        branch_id="root",
        world_time=3,
    )

    rendered = PromptRegistry().render_input(AIPromptRole.WRITER, role_input)

    assert "role-input" in rendered
    with pytest.raises(PromptRegistryError, match="Role input is for writer"):
        PromptRegistry().render_input(AIPromptRole.CRITIC, role_input)


def test_prompt_cache_scope_reuses_definition_inside_context() -> None:
    registry = PromptRegistry()
    with prompt_cache_scope():
        first = registry.get(AIPromptRole.WRITER)
        second = registry.get(AIPromptRole.WRITER)
        assert first is second


def test_repair_prompt_contains_role_schema_and_diagnostics() -> None:
    prompt = PromptRegistry().render_repair(
        AIPromptRole.SIMULATOR,
        invalid_output="{bad json}",
        diagnostics='[{"path":"state_patch.operations","code":"missing"}]',
    )

    assert "simulator" in prompt
    assert "simulation-result" in prompt
    assert "state_patch.operations" in prompt
    assert "{bad json}" in prompt


def test_simulator_prompt_requires_authoritative_ids_and_clock_progress() -> None:
    prompt = PromptRegistry().get(AIPromptRole.SIMULATOR)

    assert prompt.semantic_version
    assert "context.authoritative_ids" in prompt.content
    assert "character_profiles" in prompt.content
    assert "exactly one" in prompt.content
    assert "clock-only" in prompt.content
    assert "do not return `state_patch: null`" in prompt.content
    assert "register_location" in prompt.content
    assert "context.location_catalog" in prompt.content
    assert "context.current_locations" in prompt.content
    assert "same status" in prompt.content


def test_runtime_prompts_use_public_character_profiles_for_consistency() -> None:
    registry = PromptRegistry()

    for role in (
        AIPromptRole.PLANNER,
        AIPromptRole.SIMULATOR,
        AIPromptRole.VALIDATOR,
        AIPromptRole.WRITER,
        AIPromptRole.CRITIC,
    ):
        assert "character_profiles" in registry.get(role).content
        assert "current_locations" in registry.get(role).content


def test_world_builder_prompt_example_is_a_valid_structured_background_seed() -> None:
    content = PromptRegistry().get(AIPromptRole.WORLD_BUILDER).content
    example = json.loads(content.split("```json", 1)[1].split("```", 1)[0])

    seed = AIContractRegistry().parse(AIPromptRole.WORLD_BUILDER, example)

    assert isinstance(seed, WorldSeed)
    assert seed.goals
    assert seed.initial_relationships
    assert seed.tensions
    assert seed.threads
    assert any(claim.predicate == "secret_exists" for claim in seed.initial_claims)
    for character in (seed.player_character, *seed.npc_profiles):
        assert character.goal_ids
        assert any(
            claim.subject_id == character.character_id
            and claim.predicate == "public_fact"
            and claim.qualifiers.get("source") == "character_background"
            for claim in seed.initial_claims
        )
        assert any(character.character_id in thread.participant_ids for thread in seed.threads)
    assert "Never use `world`" in content


def test_world_builder_reports_missing_background_claim_and_unknown_world_subject_together() -> None:
    content = PromptRegistry().get(AIPromptRole.WORLD_BUILDER).content
    payload = json.loads(content.split("```json", 1)[1].split("```", 1)[0])
    payload["initial_claims"] = [
        claim for claim in payload["initial_claims"] if claim["subject_id"] != payload["player_character"]["character_id"]
    ]
    global_claim = json.loads(json.dumps(payload["initial_claims"][0]))
    global_claim.update(
        {
            "proposal_id": "claim_global_world_rule",
            "subject_id": "world",
            "typed_value": "Memories can be harvested into crystals.",
            "qualifiers": {"source": "world_rules"},
        }
    )
    payload["initial_claims"].append(global_claim)

    with pytest.raises(AIContractValidationError) as captured:
        AIContractRegistry().parse(AIPromptRole.WORLD_BUILDER, payload)

    codes = {item.code for item in captured.value.diagnostics}
    assert "structured_background_claim_missing" in codes
    assert "unknown_entity_reference" in codes
    assert "omit global world-rule claims" in str(captured.value)


def test_missing_prompt_variable_is_a_clear_error() -> None:
    definition = PromptRegistry().get(AIPromptRole.CRITIC)

    with pytest.raises(PromptRegistryError, match="missing variables"):
        definition.render({})


def test_world_builder_example_versions_follow_manifest() -> None:
    definition = PromptRegistry().get(AIPromptRole.WORLD_BUILDER)
    example = json.loads(definition.content.split("```json", 1)[1].split("```", 1)[0])
    assert example["prompt_version"] == definition.semantic_version
    assert all(claim["provenance"]["prompt_version"] == definition.semantic_version for claim in example["initial_claims"])
    assert definition.input_contract == "world-builder-input"


def test_shared_clock_is_expanded_once_and_changes_prompt_hash(tmp_path: Path) -> None:
    root = tmp_path / "prompts"
    shutil.copytree(PromptRegistry.default_root, root)
    before = PromptRegistry(root)
    old = {role: before.get(role) for role in before.roles()}
    shared = root / "shared" / "story_time.md"
    shared.write_text(shared.read_text() + "A new shared temporal rule.\n")
    after = PromptRegistry(root)
    for role in before.roles():
        definition = after.get(role)
        if role == AIPromptRole.WORLD_BUILDER:
            assert old[role].template_hash == definition.template_hash
        else:
            assert definition.content.count("Story time is authoritative.") == 1
            assert "{{>" not in definition.content
            assert old[role].template_hash != definition.template_hash


@pytest.mark.parametrize("include", ["shared/missing.md", "../outside.md"])
def test_invalid_shared_template_fails_clearly(tmp_path: Path, include: str) -> None:
    root = tmp_path / "prompts"
    shutil.copytree(PromptRegistry.default_root, root)
    (tmp_path / "outside.md").write_text("outside registry")
    path = root / "writer.md"
    path.write_text(path.read_text().replace("shared/story_time.md", include))
    with pytest.raises(PromptRegistryError, match="inside registry root"):
        PromptRegistry(root).get(AIPromptRole.WRITER)


def test_repair_system_and_user_sections_are_both_hashed(tmp_path: Path) -> None:
    root = tmp_path / "prompts"
    shutil.copytree(PromptRegistry.default_root, root)
    before = PromptRegistry(root).get_repair()
    path = root / "repair.md"
    path.write_text(path.read_text().replace("# System\n\n", "# System\n\nPreserve the branch boundary.\n"))
    after = PromptRegistry(root).get_repair()
    assert before.template_hash != after.template_hash
    path = root / "repair.md"
    path.write_text(path.read_text() + "Keep original scene IDs.\n")
    assert after.template_hash != PromptRegistry(root).get_repair().template_hash


def test_legacy_validator_role_is_rejected() -> None:
    from src.application.contracts.providers import LogicalRole

    for role_type in (AIPromptRole, LogicalRole):
        with pytest.raises(ValueError):
            role_type("context_validator")
    with pytest.raises(ValueError):
        PromptRegistry().get("context_validator")
    with pytest.raises(ValueError):
        AIContractRegistry().parse("context_validator", {})


def test_writer_and_critic_branch_language_guidance_by_story_language() -> None:
    registry = PromptRegistry()

    input_vi = RoleInput(
        input_schema_version="role-input",
        role=AIPromptRole.WRITER,
        run_id="run-vi",
        context_manifest_id="manifest-vi",
        branch_id="root",
        world_time=100,
        context={"story_language": "vi"},
    )
    rendered_vi = registry.render_input(AIPromptRole.WRITER, input_vi)
    assert "Vietnamese (`vi`)" in rendered_vi
    assert "English (`en`)" not in rendered_vi

    input_en = RoleInput(
        input_schema_version="role-input",
        role=AIPromptRole.WRITER,
        run_id="run-en",
        context_manifest_id="manifest-en",
        branch_id="root",
        world_time=100,
        context={"story_language": "en"},
    )
    rendered_en = registry.render_input(AIPromptRole.WRITER, input_en)
    assert "English (`en`)" in rendered_en
    assert "Vietnamese (`vi`)" not in rendered_en

    critic_vi = RoleInput(
        input_schema_version="role-input",
        role=AIPromptRole.CRITIC,
        run_id="run-vi-critic",
        context_manifest_id="manifest-vi-critic",
        branch_id="root",
        world_time=100,
        context={"story_language": "vi"},
    )
    rendered_critic_vi = registry.render_input(AIPromptRole.CRITIC, critic_vi)
    assert "Vietnamese (`vi`)" in rendered_critic_vi
    assert "English (`en`)" not in rendered_critic_vi
