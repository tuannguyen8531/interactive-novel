# Domain model and glossary

This is the domain contract for the project. Field names below describe the
canonical model; DTOs and APIs may present them differently but must not change
their meaning or remove provenance and scope.

## 1. General conventions

- Domain IDs are UUIDs stored as `TEXT`; SQLite row IDs are not identities.
- Audit timestamps are UTC; story time is an independent `InWorldClock`.
- Every record has a `schema_version` when its schema can evolve.
- Branch, time, and owner are mandatory scopes for queries that could expose
  knowledge.
- `provenance` contains at least source type, source ID, turn/run ID, and
  prompt/model metadata when the source is AI.

## 2. Glossary

| Term | Canonical meaning |
|---|---|
| World | A reusable universe: premise, canon, locations, seeded characters, policy, and story language |
| Playthrough | One play session for a World, with a player, clock, RNG, and root branch |
| Branch | A timeline with an independent parent, fork, and head |
| Revision | The canonical version number of a branch head |
| Turn | One action/input and its atomically committed result |
| Event | Something that actually happened; immutable after commit |
| Canon | The set of things the engine determines to be true in the world |
| KnowledgeClaim | A typed proposition with subject, predicate, object/value, and scope |
| CanonFact | An authoritative assertion about a KnowledgeClaim |
| Observation | A proposition an observer received from an event or source |
| Belief | A proposition a character believes, which may be wrong |
| ClaimLink | An evidence relationship between claims |
| StatePatch | A list of typed state operations before Guard approval |
| SceneSpec | The outcome/details approved for the Writer to express |
| NarrativeThread | A conflict or goal line currently in progress |
| NarrativeHook | A setup/payoff cue attached to an event or thread |
| Derived artifact | Data that can be deleted and rebuilt entirely from canonical data |
| Logical role | An AI contract such as Planner or Writer |
| Physical call | An actual model request that may serve several roles |
| World time | Story time measured as integer minutes from the world epoch |
| Consent | Permission for a specific activity; not a relationship score |
| Content boundary | A topic/rating limit configured by the World or player |

## 3. Aggregates and identity

Canonical character IDs and persistence-record IDs are UUID strings assigned by
the application when a WorldSeed is confirmed. Model-generated character IDs
are temporary references; confirmation remaps them and every dependent
reference atomically. Display names are not identities and may be shared by
different worlds.

Each persisted character has a structural `role` of `player` or `npc`. This is
separate from the free-form story role in the character's public profile. A
Playthrough's `player_character_id` references the UUID of the character whose
structural role is `player`.

### World

A World contains the premise, genre/tone, canon rules, locations, character
templates, content policy, initial claims, initial threads/hooks, and schema
version. Its canonical `story_language` (`en` or `vi`) is copied from the
confirmed WorldSeed and governs player-facing narrative, names, dialogue, and
suggested actions for every subsequent turn. A World does not contain the
current state of a playthrough.

The confirmed WorldSeed supplies the initial location catalog, but it is not a
closed map. A turn may canonically introduce an immediately needed place with
`RegisterLocation(location)` and then move characters there in the same
ordered patch. Dynamically registered locations carry a stable lowercase
snake-case ID, story-language name, and description. They are branch-scoped by
the patch history and become available to later turns through the canonical
location catalog; merely mentioning a place in prose does not register it.

### Playthrough

A Playthrough references a World and has a player character, root branch,
provider/config snapshot, `InWorldClock`, RNG seed/state, and an
`active/completed/archived` lifecycle.

### Branch

A Branch has a parent, fork turn/depth, head turn, head revision, and an
`active/abandoned` lifecycle. A canonical query resolves ancestors through the
fork point inclusively and then applies local events; siblings and future events
after the fork do not belong to the branch.

### Turn

A Turn stores raw input, normalized input, base revision, parent turn, status
`queued/running/completed/failed/cancelled`, final narrative, approved patch,
config/prompt versions, world-time interval, token/timing metadata, and
`turn_run_id`. `committing` is an internal/SSE phase; status becomes `completed`
only after a successful transaction.

## 4. Characters and psychology

`CharacterProfile` is stable: identity/aliases, age anchor, role/background,
appearance/voice, traits, values, boundaries, long-term goals, likes/dislikes,
and initial secrets.

`background` is a stable public profile used to keep motives, voice, and reactions
consistent; it must not contain secrets. When the World Builder creates a draft,
long-lived details are also proposed as typed claims, goals, directed
relationships, triadic tension, and narrative threads. Secrets belong in
owner-scoped private claims and must not be placed in shared character context.
The current draft format requires every character to link at least one owned
goal, one public background claim, and one thread. Private NPC claims are
available to Simulator and Validator as internal motivation; Writer and
Critic do not receive that context.

`CharacterState` changes over time: location, physical condition, emotional
state, short-term goals, attention target, stress/fatigue, inventory reference,
and last active turn. Do not modify the profile to store temporary emotion.

`PsychologicalState` minimally contains valence, arousal, dominance/control,
stress, fatigue, needs, active goals, appraisals, and suppressed emotions.
Simulator may use only beliefs, relationships, and context authorized for its
role.

The player has a profile/state like any other entity, but player intent is the
primary source for expressed actions and emotions; AI cannot write hidden
thoughts that contradict the input. Hidden player state may only be created by a
typed operation with an explicit policy.

## 5. Events, claims, observations, and beliefs

### Event

An immutable Event has a type, world time, location, actors, targets, witnesses,
structured payload, salience, emotional intensity, cause references, turn, and
branch. An off-screen event uses the same contract and does not have a looser
schema.

### KnowledgeClaim and CanonFact

```text
KnowledgeClaim:
  claim_id
  claim_type
  subject_id
  predicate
  object_id | typed_value
  polarity
  qualifiers
  valid_time
  branch_scope
  schema_version
  normalized_fingerprint
  provenance

CanonFact:
  fact_id, claim_id
  status: active | retracted | superseded
  source_event_or_rule
  asserted_turn, asserted_world_time
  superseded_by
```

The school-romance MVP has a finite, versioned predicate registry:

| Predicate | Subject/object or value | Purpose |
|---|---|---|
| `located_at` | character/location | Canonical location at a world time |
| `age_is` | character/integer | Age at valid time |
| `romantic_interest` | character/character | Directed romantic feeling |
| `commitment_status` | character/character/enum | Commitment event/state |
| `goal_active` | character/goal ID | Goal currently being pursued |
| `secret_exists` | owner/secret ID | Typed secret, not free text |
| `item_held` | character/item ID | Item currently held |
| `physical_condition` | character/enum/value | Physical condition |
| `public_fact` | entity/typed value | Authorized public fact |
| `event_participation` | character/event ID | Actor or witness participation |

New claims require a registered schema and migration. Relationship deltas,
clock advances, thread transitions, and character-state deltas are separate
typed `StateOperation`s; the predicate registry must not be used to bypass
policy.

The normalized fingerprint includes subject, predicate, object-or-value,
polarity, qualifiers, valid time, and branch scope with deterministic key
ordering. Claim ID is distinct from fact identity.

### Observation

An Observation contains an observer, source event/information, observed claim,
method (`saw/heard/told/inferred`), confidence, distortion, timestamp, and
claim links.

### Belief

A Belief contains a believer, claimed proposition, stance
(`supports/rejects/uncertain`), confidence, evidence/counter-evidence, source
reliability, and created/updated turn. A Belief cannot assert a CanonFact by
itself.

## 6. StatePatch and authority

`StatePatch` is a list of typed operations, for example:

- `AdvanceClock(duration_minutes)`;
- `RegisterLocation(location)`;
- `SetCharacterLocation(character_id, location_id)`;
- `SetCharacterCondition(character_id, condition)`;
- `UpdatePsychology(character_id, typed_delta)`;
- `ApplyRelationshipDelta(source, target, dimension, proposed_delta, cause)`;
- `AddKnowledgeClaim(claim)` / `AssertCanonFact(claim_id)`;
- `AddObservation(observation)` / `UpdateBelief(belief)`;
- `TransitionThread(thread_id, status, progress_delta)`;
- `MaterializeScheduledEvent(event)`.

Simulator only proposes operations. Guard checks IDs, ranges, branch/time,
authorization, content policy, idempotency, and state transitions. The
Canonical Record Builder accepts only Guard-approved patches; prose is not an
authoritative input. `RegisterLocation` must precede any operation that uses
the new ID, and duplicate or malformed location registrations are rejected.
An `active` or `escalating` narrative thread may apply a non-zero progress
delta while retaining its current lifecycle status; a zero-delta same-status
transition and every terminal-thread revival remain invalid.

## 7. Relationships and tension

A Relationship is a directed edge with dimensions defined by the domain
contract. Every change log records before/proposed/validated/after values, cause
event, reason, LLM run, and prompt version. Labels such as `friend`, `crush`,
`lover`, and `rival` are derived projections; `lover` requires commitment
evidence.

`EmotionalTension` uses observer/rival/focus/trigger/intensity/appraisal/decay/
visibility to represent jealousy and triadic misunderstanding.

## 8. Narrative threads and hooks

A Thread has a premise, participants, status (`seeded`, `active`, `escalating`,
`resolved`, `abandoned`), stakes, progress, urgency, last advanced turn, and
resolution conditions. A Hook has a setup, expected payoff window, related
memory/event, visibility, and status. Memory retrieval does not replace thread
management.

## 9. Clock, RNG, and policy visibility

`InWorldClock` uses integer minutes from an epoch; each turn has a
start/duration/end, with duration proposed by Simulator and validated by Guard.
Invalid durations are rejected rather than silently clamped. Completed player
turns without positive clock movement receive the default one-minute advance.
The epoch is midnight on Day 1: 930 means Day 1 at 15:30, while 1530 means
Day 2 at 01:30. Values are never interpreted as HHMM.

Every turn role receives engine-derived `context.clock.current` with the minute
count, day, 24-hour time and conventional period (night 22–06, morning 06–12,
afternoon 12–18, evening 18–22). These periods do not model astronomical daylight.
Writer and Critic also receive the approved duration and end time, including
midnight crossings. Prompts require temporal consistency with these values;
semantic lighting consistency is checked by AI, not a deterministic sunlight
rule. The World Builder preview displays the converted opening time before
confirmation. Existing saves are not reinterpreted or migrated by this change.

Branches inherit the clock at the fork and then advance independently. UTC
timestamps are audit data only.

RNG is seeded and stored per playthrough/branch; only declared rules or checks
may use it. Replay must reuse the RNG state.

Player mode shows the transcript, permitted scene state, and ambiguous
relationship labels; developer mode can inspect claims, beliefs, evidence,
vectors, hidden goals, retrieval traces, and LLM metadata.

## 10. Source-of-truth rules

- CanonFact, current state, and event are authoritative.
- Observation and Belief are perspective-specific authority about what a
  character received or believes, not world truth.
- Narrative summaries, embeddings, retrieval indexes, and snapshots are derived.
- LangGraph checkpoints are execution artifacts.
- When derived data is missing or stale, the read path falls back to canonical
  state and raw events.
