# ContentPolicy schema and deterministic enforcement

This is the policy contract for the World Builder, domain Guard, Writer, and
Critic. It must not be represented only as prompt text.

## 1. Normalized schema

```text
ContentPolicy {
  schema_version: string
  rating: teen_14_plus | mature_16_plus | adult_18_plus
  topic_boundaries: map<TopicTag, allow | opt_in | excluded>
  violence_ceiling: none | restrained | detailed
  adult_explicit_opt_in: bool
  consent: {
    required: bool
    explicit_affirmative: bool
    withdrawal_supported: bool
  }
  player_overrides: optional ContentPolicyOverride
}
```

A player override is not an independent policy that can loosen the World.
Effective policy takes the stricter value for each field; `excluded` cannot be
changed to `allow` during a turn. `adult_explicit_opt_in` is effective only when
the World rating is also `adult_18_plus`.

The MVP supports these topic-boundary tags:

| Group | Tags |
|---|---|
| Romance | `romantic_affection`, `dating`, `kiss`, `non_graphic_intimacy` |
| Mature | `mature_emotional_theme`, `sexual_reference_fade_to_black` |
| Adult | `adult_explicit`, `sexualized_nudity`, `fetishization` |
| Safety | `grooming`, `exploitation`, `non_consensual_sexual` |
| Violence | `violence`, `violence:torture`, `sexual_violence` |
| Sensitive | `psychological_harm`, `loss`, `complex_relationship` |

New tags require a schema version, meaning, allowed rating, and fixture. A
relationship score must not be used to infer consent or adult eligibility.

## 2. Scene age gate

Age is evaluated at `SceneSpec.world_time`, not when the World is created.

| Participant age | Allowed | Forbidden |
|---:|---|---|
| 14–15 | Crushes, dating, hand-holding, hugs, light kissing, emotional conflict | Sexualization, explicit nudity, fetishization, sexual behavior |
| 16–17 | Mature emotional themes, boundaries, jealousy, breakup, non-graphic intimacy | Explicit sexual description; eroticized sexual activity |
| 18+ | Adult themes/explicit content only when every other gate passes | Missing opt-in, missing consent, excluded topic, exceeding violence ceiling |

An adult/minor relationship must not be presented as positive romance; grooming
and exploitation are always denied. A timeskip cannot retroactively change a
decision or the history of an existing scene.

## 3. Consent state machine

A consent record has `scene_id`, participant, activity tag, state, `requested_at`,
`decided_at`, source/evidence, and withdrawal metadata. Valid transitions are:

```text
not_discussed → requested
requested → granted | declined
declined → requested
granted → withdrawn
withdrawn → requested
```

`granted` must be affirmative and activity-specific, and it can be withdrawn.
Silence, fear, intoxication, a prior relationship, prior consent, or strong
attraction is not a grant. Every adult participant in an explicit scene must
have a valid consent record.

## 4. Violence ceiling and topic decisions

`SceneSpec` represents content type and description level in two independent
fields:

```text
content_tags: violence | violence:torture | sexual_violence | ...
violence_detail: none | restrained | detailed
```

Torture is a subtype of violence. Sexual violence is subject to the violence
ceiling and may also be restricted independently through `topic_boundaries`.

| Scene content | `none` | `restrained` | `detailed` |
|---|---:|---:|---:|
| Violence | deny | allow restrained | allow restrained/detailed |
| `violence:torture` | deny | allow restrained | allow restrained/detailed |
| `sexual_violence` | deny | allow restrained | allow restrained/detailed |

- `none`: violent actions or consequences may not be described.
- `restrained`: content may occur without vivid physical detail, gore,
  anatomy, or an extended description of suffering.
- `detailed`: direct description of the action and physical consequences is
  allowed.
- `topic_boundaries.* = excluded` always denies the topic regardless of the
  ceiling.
- A provider refusal must not be bypassed through fallback; retry only with a
  valid request or perform an explicit downgrade.

The loader still accepts `non_graphic` and `graphic` from legacy world data and
normalizes them to `restrained` and `detailed`.

## 5. Deterministic evaluation order

The Guard evaluates in this order and stops on an error that cannot be
downgraded:

1. Schema, tag, participant, and reference existence.
2. The age of every participant at world time.
3. Adult/minor romance and age-inappropriate explicit content.
4. The violence ceiling from the scene content type and detail level.
5. Topic boundaries and the effective player policy.
6. Rating, explicit opt-in, and consent for adult activities.
7. If the beat remains valid after removing forbidden detail, return
   `downgrade` with a safe SceneSpec; otherwise return `deny`.

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

## 6. Enforcement points

1. World Builder validates age, rating, warnings, boundaries, and the initial
   scene.
2. Planner and Simulator receive the policy as a mandatory constraint.
3. Claim Extractor attaches participants, age, consent, and content tags.
4. Guard makes the deterministic decision before producing SceneSpec.
5. Writer receives only tags and description levels that are allowed.
6. Critic looks for tags or details that exceed policy in the final draft; Critic
   cannot grant canon authority or override Guard.

Executable design fixtures live at
`tests/fixtures/scenarios/content_policy.json`; deterministic Guard tests run
against this fixture and the subtype × violence-ceiling matrix.
