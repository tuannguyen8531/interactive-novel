# MVP architecture

This document defines module ownership and the architecture contract for the
current runtime. The scope is a local-first, single-player, text-first
narrative simulation engine, not a chat transcript.

## 1. Authority principles

```text
LLM             understands intent, proposes, simulates, writes, critiques
Domain engine   checks rules, normalizes claims, clamps mutations, decides
Persistence     records truth, history, branches, revisions, and provenance
```

The LLM must not decide the final outcome, create canon from narrative text, or
cross a knowledge boundary. Every authoritative fact or state mutation must be
a typed `KnowledgeClaim` or typed state operation before the Guard can approve
and commit it.

## 2. Module boundaries

```text
Vue 3 frontend
  play / builder / saves / inspector
           │ REST + SSE
           ▼
FastAPI API
  routes / DTOs / auth / jobs
           │ use-case ports
           ▼
Application layer
  use cases / retrieval / transactions
      ├── Graph
      │   turn orchestration / run state
      ├── Domain
      │   rules / claims / policies
      └── Services
          SQLite / checkpoints / LLM / logs
```

The dependency direction is:

```text
api → application → domain
graph → application contracts + domain policies
services → implements ports declared inward
domain → does not import FastAPI, SQLAlchemy, LangGraph, or provider SDKs
```

`api` and `cli` are thin adapters. `application` owns use cases and the
transaction boundary. `domain` owns pure invariants. `graph` coordinates
contracts but does not own truth. `services` implement persistence, LLM,
embedding, and logging ports declared by inward-facing layers.

## 3. Data ownership

| Artifact | Owner | Canonical/derived | Write authority |
|---|---|---|---|
| World | World use cases + domain validation | Canonical | User confirmation or migration |
| Playthrough | Playthrough service | Canonical | Application transaction |
| Branch/head/revision | Branch + commit service | Canonical | Optimistic head update |
| Turn/narrative | Turn commit service | Canonical | Insert once; correction is a new record |
| Event/participants | Canonical record builder | Canonical | Append-only after commit |
| KnowledgeClaim/CanonFact | Claim registry + Guard + commit | Canonical | Typed assertion/retraction |
| Observation/Belief/evidence | Knowledge service + commit | Canonical | According to owner and source |
| CharacterProfile | World | Canonical | Draft confirmation/migration |
| CharacterState/Psychology | Turn commit service | Canonical current state | Typed state patch |
| Relationship/Change/Tension | Relationship policy + commit | Canonical | Policy-validated delta |
| Thread/Hook | Thread policy + commit | Canonical | Typed transition |
| Snapshot | Derived builder | Derived | Rebuildable, checksummed, versioned |
| Summary/embedding/index | Derived workers | Derived | Rebuildable, not authoritative |
| LangGraph checkpoint | Graph/checkpoint service | Execution state | Not a save |

Every canonical record carries `playthrough_id`, `branch_id`, a revision or
turn, and appropriate provenance. The API never returns ORM records directly.

The confirmed WorldSeed also persists its `story_language` (`en` or `vi`) in
the World canon. Settings choose the default for new drafts; turn context
reads the World value so changing the default never changes an existing story.

## 4. Turn flow and authority boundary

```text
raw input
  → normalize_input
  → initial context + hard-scoped retrieval + bounded public character profiles
  → Planner artifact
  → Simulator artifact
  → Claim Extractor / typed proposed operations
  → targeted consistency retrieval
  → Context Validator report
  → deterministic State Guard
  → approved StatePatch + SceneSpec
  → Writer draft
  → Critic / bounded revision
  → Canonical Record Builder
  → one transaction: canonical records + branch head
  → SSE completed
  → derived outbox jobs
```

Initial context includes at most four related characters (the actor, mentioned
characters, and people at the same location); each background has a length
limit. Planner, Simulator, Writer, and Critic use these public profiles to keep
motives and behavior consistent. Quantified relationships and tension are
available only to planning, simulation, and validation roles; Writer and Critic
do not receive internal scores. Private claims and secrets are retrieved only
when `owner_id` matches the authorized owner. For related NPCs, owner-scoped
private claims are joined directly into the internal context of Simulator and
Context Validator so they influence choices without appearing in public
initial context, Planner, Writer, or Critic context.

The current WorldSeed format passes validation only when each character has at
least one owned goal, one public typed claim with
`source=character_background`, and participation in at least one narrative
thread. Every private claim must be linked by its owner through
`private_claim_ids`. After confirmation, typed claims become CanonFacts; prose
background remains a public profile and has no mutation authority by itself.
Validation also rejects public background that directly contains a private
claim identifier or text value; indirect semantic disclosure remains controlled
by the prompt and Context Validator. WorldSeed v1.5 allows
`initial_claims.subject_id` to refer only to declared characters or locations;
global world rules remain in premise or canon prose. Preflight groups related
coverage and cross-reference errors into one diagnostic set so a single
structured-output repair can fix the complete payload instead of failing one
invariant at a time.

Writer receives `SceneSpec`, authorized evidence, bounded public character
profiles, and the canonical story language; it does not receive the whole
database, internal relationship or tension scores, and it does not return a
state patch. Critic cannot change the outcome or state. Guard is the final
deterministic gate before commit.

## 5. Canonical transaction

The application commit service opens a transaction and checks that
`base_revision` is still the branch head. The same transaction records the turn,
final narrative, events, claims/facts/links, observations/beliefs/evidence,
state, relationships, tensions, threads/hooks, outbox intent, and head/revision.
Any error before commit rolls back the complete operation.

Only after commit does the system send SSE `completed`. Summary, snapshot,
embedding, retrieval index, consolidation, and analytics run outside the
transaction; their failures create retry or reconciliation work only.
Canonical reads do not depend on derived artifacts.

## 6. Knowledge and context boundary

Initial and targeted retrieval both apply hard filters for:

1. playthrough;
2. branch ancestry and fork boundary;
3. world time;
4. owner/observer;
5. entity/thread scope.

Semantic or vector ranking runs only on the filtered candidate set. Exact claims
and fingerprints take priority; other queries combine rule/keyword score (55%)
with cosine similarity (45%). Vector memory is stored in SQLite with source ID,
content hash, model, and embedding version; each search creates a new embedding
only for the query. If a provider or vector path is unavailable, retrieval
falls back to deterministic ranking. Context manifests and retrieval traces
record IDs, scopes, scores, match reasons, model, revision, budget, and role.
Simulator may receive the hidden state required for simulation; Writer receives
only the part of `SceneSpec` that is allowed to be expressed. Player mode does
not place internal beliefs, hidden goals, or numeric relationships in the
store/UI.

## 7. Logical roles and physical calls

The five logical contracts are Planner, Simulator, Context Validator, Writer,
and Critic. `PhysicalCallPlan` may split or fuse them according to Quality/Fast
mode and provider capability; tracing still creates a separate artifact or
validator record for each logical role. No mode may bypass the deterministic
Guard. Quality/Fast is an execution policy, not two domain semantics.

## 8. Runtime and persistence boundary

```text
runtime/
├── game.db          # canonical product data
├── checkpoints.db   # LangGraph execution checkpoint
├── logs/
│   ├── telemetry.jsonl  # opt-in, secret-free profiling
│   └── feedback.jsonl   # explicit alpha feedback
└── exports/
settings.json       # non-secret UI/provider choices
```

SQLite uses WAL, foreign keys, a busy timeout, and one active turn per branch.
Secrets remain in the environment or OS keyring; raw prompts and outputs are
not stored by default.

## 9. Locked product decisions

- The first MVP template is school romance with 1–3 main NPCs.
- POV is configured per playthrough and defaults to second person.
- The player has a profile and state to preserve what actions express, but AI
  cannot invent hidden thoughts that contradict the input.
- Player mode shows ambiguous relationship signals/labels; developer mode can
  inspect numeric vectors and hidden state.
- RNG is seeded per playthrough/branch and is used only by declared rules or
  checks.
- ContentPolicy, consent, and the violence ceiling are deterministic; see
  `docs/content-policy.md`.
- Off-screen behavior materializes only scheduled or thread-triggered events;
  there is no autonomous world tick.

## 10. MVP non-goals

Do not scaffold every empty module, connect a real provider in the deterministic
slice, or build combat, multiplayer, microservices, operational PostgreSQL or
vector databases, TTS/images, mobile, a marketplace, a full
WorldScheduler/NPCAgenda/WorldTick, or autonomous rumor propagation.
