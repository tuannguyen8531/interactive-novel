from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.domain.content import ContentDecision, ContentPolicy, SceneSpec, evaluate_scene
from src.domain.errors import GuardRejected
from src.domain.guard import DomainGuard
from src.domain.state import GameState

FIXTURE = Path(__file__).parents[1] / "fixtures" / "scenarios" / "content_policy.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _policy(case: dict[str, Any]) -> ContentPolicy:
    world_name = str(case["world_policy"])
    player_name = str(case["player_policy"])
    return ContentPolicy.from_mapping(
        DATA["policy_presets"][world_name],
        player_overrides=DATA["player_presets"][player_name],
    )


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda case: case["id"])
def test_content_policy_fixture_is_deterministic(case: dict[str, Any]) -> None:
    scene_data = case["scene"]
    scene = SceneSpec(
        world_time=scene_data["world_time"],
        tags=tuple(scene_data["tags"]),
        participants=case["participants"],
        consent=scene_data["consent"],
    )
    policy = _policy(case)
    first = evaluate_scene(policy, scene)
    second = evaluate_scene(policy, scene)
    expected = case["expected"]

    assert first == second
    assert first.decision.value == expected["decision"]
    assert list(first.reason_codes) == expected["reason_codes"]
    assert list(first.safe_tags) == expected.get("safe_tags", [])

    if case["id"] == "timeskip-does-not-rewrite-history":
        history = case["history"]
        later_scene = SceneSpec(
            world_time=history["timeskip_to_world_time"],
            tags=scene.tags,
            participants={"a": history["a_age_after_timeskip"], "b": history["b_age_after_timeskip"]},
            consent=scene.consent,
        )
        later_decision = DomainGuard().validate_scene(
            GameState.empty(branch_id="root", world_time=later_scene.world_time, policy=policy),
            later_scene,
        )
        assert later_decision.decision == ContentDecision.ALLOW
        assert first.reason_codes == ("explicit_participant_under_18",)


def test_guard_rejects_denied_scene_with_stable_code() -> None:
    policy = ContentPolicy.from_mapping(DATA["policy_presets"]["adult_world_opted_in"])
    state = GameState.empty(policy=policy)
    scene = SceneSpec(world_time=0, tags=("adult_explicit",), participants={"a": 18, "b": 18})

    with pytest.raises(GuardRejected) as error:
        DomainGuard().validate_scene(state, scene)

    assert error.value.code == "player_explicit_not_opted_in" or error.value.code == "consent_missing_or_invalid"
