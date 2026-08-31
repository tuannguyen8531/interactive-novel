from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.domain.content import ContentDecision, ContentPolicy, SceneSpec, ViolenceCeiling, evaluate_scene
from src.domain.errors import GuardRejected
from src.domain.guard import DomainGuard
from src.domain.state import GameState

FIXTURE = Path(__file__).parents[1] / "fixtures" / "scenarios" / "content_policy.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _policy(case: dict[str, Any]) -> ContentPolicy:
    world_name = str(case["world_policy"])
    return ContentPolicy.from_mapping(DATA["policy_presets"][world_name])


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda case: case["id"])
def test_content_policy_fixture_is_deterministic(case: dict[str, Any]) -> None:
    scene_data = case["scene"]
    scene = SceneSpec(
        world_time=scene_data["world_time"],
        tags=tuple(scene_data["tags"]),
        participants=case["participants"],
        consent=scene_data["consent"],
        violence_detail=scene_data.get("violence_detail", "none"),
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
        assert first.reason_codes == ("age_16_17_explicit_not_allowed",)


def test_guard_rejects_denied_scene_with_stable_code() -> None:
    policy = ContentPolicy.from_mapping(DATA["policy_presets"]["adult_world_consent_required"])
    state = GameState.empty(policy=policy)
    scene = SceneSpec(world_time=0, tags=("adult_explicit",), participants={"a": 18, "b": 18})

    with pytest.raises(GuardRejected) as error:
        DomainGuard().validate_scene(state, scene)

    assert error.value.code == "consent_missing_or_invalid"


@pytest.mark.parametrize("tag", ("violence", "violence:torture", "sexual_violence"))
@pytest.mark.parametrize(
    ("ceiling", "detail", "expected"),
    (
        ("none", "restrained", ContentDecision.DENY),
        ("restrained", "restrained", ContentDecision.ALLOW),
        ("restrained", "detailed", ContentDecision.DENY),
        ("detailed", "restrained", ContentDecision.ALLOW),
        ("detailed", "detailed", ContentDecision.ALLOW),
    ),
)
def test_violence_ceiling_applies_the_same_detail_matrix_to_subtypes(
    tag: str,
    ceiling: str,
    detail: str,
    expected: ContentDecision,
) -> None:
    policy = ContentPolicy.from_mapping({"rating": "adult_18_plus", "violence_ceiling": ceiling})
    scene = SceneSpec(
        world_time=0,
        tags=(tag,),
        participants={"a": 18},
        violence_detail=ViolenceCeiling(detail),
    )

    assert evaluate_scene(policy, scene).decision == expected


def test_legacy_violence_values_are_normalized_when_loading_policy() -> None:
    assert ContentPolicy.from_mapping({"violence_ceiling": "non_graphic"}).violence_ceiling.value == "restrained"
    assert ContentPolicy.from_mapping({"violence_ceiling": "graphic"}).violence_ceiling.value == "detailed"
