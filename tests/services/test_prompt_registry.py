from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.application.contracts.ai import AIPromptRole, RoleInput
from src.services.prompts import PromptRegistry, PromptRegistryError, prompt_cache_scope

SNAPSHOTS = Path(__file__).parents[1] / "fixtures" / "prompts" / "phase_6_snapshots.json"


def test_prompt_snapshot_matches_golden_hashes() -> None:
    expected = json.loads(SNAPSHOTS.read_text(encoding="utf-8"))
    snapshot = PromptRegistry().snapshot()

    for role, metadata in expected.items():
        assert snapshot[role]["semantic_version"] == metadata["semantic_version"]
        assert snapshot[role]["input_contract"] == metadata["input_contract"]
        assert snapshot[role]["output_schema_version"] == metadata["output_schema_version"]
        assert snapshot[role]["template_hash"] == metadata["template_hash"]


def test_prompt_render_replaces_required_input_without_unresolved_placeholders() -> None:
    registry = PromptRegistry()
    rendered = registry.render(AIPromptRole.PLANNER, input_json='{"run_id":"turn-run-1"}')

    assert "turn-run-1" in rendered
    assert "{{" not in rendered
    assert "Return only JSON" in rendered


def test_render_input_requires_matching_versioned_role() -> None:
    role_input = RoleInput(
        input_schema_version="role-input-1",
        role=AIPromptRole.WRITER,
        run_id="turn-run-1",
        context_manifest_id="manifest-1",
        branch_id="root",
        world_time=3,
    )

    rendered = PromptRegistry().render_input(AIPromptRole.WRITER, role_input)

    assert "role-input-1" in rendered
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
    assert "simulation-result-1" in prompt
    assert "state_patch.operations" in prompt
    assert "{bad json}" in prompt


def test_missing_prompt_variable_is_a_clear_error() -> None:
    definition = PromptRegistry().get(AIPromptRole.CRITIC)

    with pytest.raises(PromptRegistryError, match="missing variables"):
        definition.render({})
