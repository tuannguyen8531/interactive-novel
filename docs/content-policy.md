# ContentPolicy schema and deterministic enforcement

This is the policy contract for the World Builder, domain Guard, Writer, and
Critic. It must not be represented only as prompt text.

## 1. Normalized schema

```text
ContentPolicy {
  schema_version: string
  rating: teen_14_plus | mature_16_plus | adult_18_plus
  violence_ceiling: none | restrained | detailed
  consent: {
    required: bool = false
    explicit_affirmative: bool
    withdrawal_supported: bool
  }
}
```

`adult_18_plus` permits explicit adult content by default.

The supported content tags are:

| Group | Tags |
|---|---|
| Romance | `romantic_affection`, `dating`, `kiss`, `non_graphic_intimacy` |
| Mature | `mature_emotional_theme`, `sexual_reference_fade_to_black` |
| Adult | `adult_explicit`, `sexualized_nudity`, `fetishization` |
| Dark | `grooming`, `exploitation`, `non_consensual_sexual` |
| Violence | `violence`, `violence:torture`, `sexual_violence` |
| Sensitive | `psychological_harm`, `loss`, `complex_relationship` |

New tags require a schema version, meaning, allowed rating, and executable
fixture. Relationship scores do not determine age eligibility or consent.

## 2. Scene age gate

Age is evaluated at `SceneSpec.world_time`, not when the World is created.

| Participant age | Allowed | Forbidden |
|---:|---|---|
| Under 14 | No playable scene participation | All scene participation |
| 14–15 | Crushes, dating, hand-holding, hugs, light kissing, emotional conflict, and non-sexual dark themes | Sexualization, explicit nudity, fetishization, sexual behavior, and sexual violence |
| 16–17 | Mature emotional themes, boundaries, jealousy, breakup, non-graphic intimacy, and fade-to-black references | Explicit sexual description, eroticized activity, fetishization, and sexual violence |
| 18+ | All registered themes, including explicit adult and dark content, subject to the violence ceiling | Content exceeding the violence ceiling |

An adult/minor relationship must not be presented as positive romance. Grooming
and exploitation may be portrayed as manipulation, abuse, conflict, or harm,
but they do not waive the age gate and cannot make sexual content involving a
minor eligible.

A timeskip cannot retroactively change a decision or rewrite the history of an
existing scene. Later scenes use the participants' ages at their own World time.

## 3. Consent as story state

Consent remains canonical story state with `scene_id`, participant, activity
tag, state, timestamps, source/evidence, and withdrawal metadata. Valid
transitions are:

```text
not_discussed → requested
requested → granted | declined
declined → requested
granted → withdrawn
withdrawn → requested
```

The default local policy has `consent.required = false`: missing consent data
does not by itself block an adult scene. This supports stories that depict
conflict, exploitation, or sexual violence. Such content must carry the
appropriate dark/violence tags rather than being mislabeled as consensual.

A World may set `consent.required = true` as a stricter creative constraint. In
that mode, every adult participant in an explicit scene needs affirmative,
activity-specific consent, and a withdrawal denies the scene.

## 4. Adult and dark content

For participants aged 18 or older, an `adult_18_plus` World may use
`adult_explicit`, `sexualized_nudity`, `fetishization`, `psychological_harm`,
`loss`, `complex_relationship`, `grooming`, and `exploitation`.

`sexual_violence` and `non_consensual_sexual` are adult-only dark-content tags.
They require an `adult_18_plus` World and remain subject to the selected violence
ceiling.

## 5. Violence ceiling and topic decisions

`SceneSpec` represents content type and description level independently:

```text
content_tags: violence | violence:torture | sexual_violence | ...
violence_detail: none | restrained | detailed
```

| Scene content | `none` | `restrained` | `detailed` |
|---|---:|---:|---:|
| Violence | deny | allow restrained | allow restrained/detailed |
| `violence:torture` | deny | allow restrained | allow restrained/detailed |
| `sexual_violence` | deny | allow restrained | allow restrained/detailed |

- `none`: violent actions or consequences may not be described.
- `restrained`: content may occur without vivid gore, anatomy, or extended
  physical suffering.
- `detailed`: direct action, gore, torture, anatomy, and physical consequences
  may be described.
- The loader accepts legacy `non_graphic` and `graphic` values and normalizes
  them to `restrained` and `detailed`.
- A provider refusal must not be bypassed through fallback. Retry with a valid
  request, perform an explicit downgrade, or use a locally operated model whose
  own capabilities permit the requested content.

## 6. Deterministic evaluation order

The Guard evaluates in this order and stops on an error that cannot be safely
downgraded:

1. Schema, tag, participant, and reference existence.
2. Every participant's age at scene World time.
3. Adult/minor romance and age-inappropriate sexual content.
4. The violence ceiling from the scene type and detail level.
5. Adult rating and any optional World-specific consent requirement.
6. If removing forbidden detail leaves a valid beat, return `downgrade` with a
   safe `SceneSpec`; otherwise return `deny`.

Minimum output:

```text
PolicyDecision {
  decision: allow | downgrade | deny
  reason_codes: list<string>
  effective_policy_version: string
  participant_ages: map<id, int>
  evaluated_tags: list<TopicTag>
  evaluated_world_time: int
}
```

## 7. Enforcement points

1. World Builder validates age, rating, warnings, violence ceiling, and the opening
   scene.
2. Planner and Simulator receive the policy as a mandatory constraint.
3. Claim Extractor attaches participants, age, consent state, and content tags.
4. Guard makes the deterministic decision before producing `SceneSpec`.
5. Writer receives only tags and detail levels allowed for that scene.
6. Critic detects tags or detail beyond policy but cannot override Guard or
   grant canon authority.

Executable fixtures live at `tests/fixtures/scenarios/content_policy.json`;
Guard tests cover the age gates, dark topics, legacy normalization, history
invariants, and subtype × violence-ceiling matrix.
