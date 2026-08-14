# Kiến trúc MVP

Tài liệu này cụ thể hóa các ADR trong `docs/adr/` và là contract ownership cho
những Phase tiếp theo. Phạm vi là narrative simulation engine local-first,
single-player, text-first; không phải chatbot nối văn bản.

## 1. Nguyên tắc authority

```text
LLM             hiểu ý định, đề xuất, mô phỏng, viết, phê bình
Domain engine   kiểm tra rule, normalize claim, clamp mutation, quyết định
Persistence     ghi sự thật, lịch sử, branch, revision và provenance
```

LLM không được quyết định outcome cuối, không được tự tạo canon từ narrative
text và không được vượt knowledge boundary. Mọi authoritative fact/state
mutation phải là typed `KnowledgeClaim` hoặc typed state operation trước khi
được Guard và commit.

## 2. Ranh giới module

```text
┌─────────────────────────────────────────────────────┐
│ Vue 3: play UI, builder, saves, inspector            │
└──────────────────────┬──────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼──────────────────────────────┐
│ FastAPI: routes, DTO, auth boundary, job coordinator │
└──────────────────────┬──────────────────────────────┘
                       │ use-case ports
┌──────────────────────▼──────────────────────────────┐
│ Application: worlds, playthroughs, turns, branches, │
│ retrieval queries và transaction orchestration        │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
┌──────────────▼──────────────┐  ┌───▼────────────────┐
│ Graph: turn orchestration    │  │ Domain: rules,     │
│ và bounded run state          │  │ claims, policies  │
└──────────────┬──────────────┘  └───┬────────────────┘
               │                      │ ports/contracts
┌──────────────▼──────────────────────▼────────────────┐
│ Services: SQLite, checkpoint, LLM, embeddings, logs  │
└───────────────────────────────────────────────────────┘
```

Hướng phụ thuộc là:

```text
api → application → domain
graph → application contracts + domain policies
services → implements ports declared inward
domain → không import FastAPI, SQLAlchemy, LangGraph hoặc provider SDK
```

`api` và `cli` là adapter mỏng. `application` sở hữu use-case và transaction
boundary. `domain` sở hữu invariant thuần. `graph` điều phối các contract; nó
không trở thành nơi sở hữu sự thật. `services` hiện thực port persistence,
LLM, embedding và logging được khai báo ở lớp hướng vào.

## 3. Ownership của dữ liệu

| Artifact | Owner | Canonical/derived | Quyền sửa |
|---|---|---|---|
| World | World use cases + domain validation | Canonical | User confirm hoặc migration |
| Playthrough | Playthrough service | Canonical | Application transaction |
| Branch/head/revision | Branch + commit service | Canonical | Optimistic head update |
| Turn/narrative | Turn commit service | Canonical | Insert một lần; correction là record mới |
| Event/participants | Canonical record builder | Canonical | Append-only sau commit |
| KnowledgeClaim/CanonFact | Claim registry + Guard + commit | Canonical | Typed assertion/retraction |
| Observation/Belief/evidence | Knowledge service + commit | Canonical | Theo owner và source |
| CharacterProfile | World | Canonical | Draft confirm/migration |
| CharacterState/Psychology | Turn commit service | Canonical current state | Typed state patch |
| Relationship/Change/Tension | Relationship policy + commit | Canonical | Policy-validated delta |
| Thread/Hook | Thread policy + commit | Canonical | Typed transition |
| Snapshot | Derived builder | Derived | Rebuildable, checksum/version |
| Summary/embedding/index | Derived workers | Derived | Rebuildable, không authority |
| LangGraph checkpoint | Graph/checkpoint service | Execution state | Không phải save |

Một record canonical luôn gắn `playthrough_id`, `branch_id`, revision/turn và
provenance phù hợp. API không trả ORM record trực tiếp.

## 4. Luồng một turn và authority boundary

```text
raw input
  → normalize_input
  → initial context + hard-scoped retrieval
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

Writer chỉ nhận `SceneSpec` gồm beat, visible action, allowed dialogue intent,
POV, tone, continuity details, allowed/restricted facts và length target. Writer
không nhận toàn bộ database và không trả state patch. Critic không đổi outcome
hoặc state. Guard là cửa deterministic cuối cùng trước commit.

## 5. Canonical transaction

Application commit service mở transaction và kiểm tra `base_revision` còn là
branch head. Trong cùng transaction ghi turn, final narrative, events,
claims/facts/links, observations/beliefs/evidence, state, relationships,
tensions, threads/hooks, outbox intent và head/revision. Lỗi ở bất kỳ bước nào
trước commit đều rollback toàn bộ.

Sau commit mới gửi SSE `completed`. Summary, snapshot, embedding, retrieval
index, consolidation và analytics chạy ngoài transaction; lỗi của chúng chỉ
tạo retry/reconcile. Canonical read không phụ thuộc artifact derived.

## 6. Knowledge và context boundary

Initial retrieval và targeted retrieval đều áp hard filter theo:

1. playthrough;
2. branch ancestry và fork boundary;
3. world time;
4. owner/observer;
5. entity/thread scope.

Semantic/vector ranking chỉ chạy trên candidate đã được filter. Context manifest
ghi IDs, scopes, revision, budget và role. Simulator có thể nhận hidden state
cần để mô phỏng; Writer chỉ nhận phần SceneSpec cho phép biểu đạt. Player mode
không đưa internal beliefs, hidden goals hay numeric relationship vào store/UI.

## 7. Logical role và physical call

Năm logical contracts là Planner, Simulator, Context Validator, Writer, Critic.
`PhysicalCallPlan` có thể split/fuse theo Quality/Fast và capability; trace vẫn
tạo artifact/validator riêng cho từng logical role. Không mode nào bỏ
deterministic Guard. Quality/Fast là execution policy, không phải hai domain
semantics.

## 8. Runtime và persistence boundary

```text
runtime/
├── game.db          # canonical product data
├── checkpoints.db   # LangGraph execution checkpoint
├── logs/
└── exports/
settings.json       # non-secret UI/provider choices
```

SQLite dùng WAL, foreign keys, busy timeout và một active turn trên mỗi branch.
Secrets ở environment/OS keyring; raw prompts/outputs không lưu mặc định.

## 9. Các quyết định sản phẩm đã khóa

- Template MVP đầu tiên là school romance, 2–4 NPC chính.
- POV cấu hình theo playthrough; mặc định là ngôi thứ hai.
- Player có profile/state để lưu trạng thái thể hiện qua hành động, nhưng AI
  không tự phát minh hidden thoughts trái input.
- Player mode thấy tín hiệu/nhãn quan hệ mơ hồ; developer mode mới thấy vector
  số và hidden state.
- RNG được seed theo playthrough/branch và chỉ dùng ở rule/check đã khai báo.
- ContentPolicy, consent và violence ceiling là deterministic; xem
  `docs/content-policy.md`.
- Off-screen chỉ materialize ScheduledEvent/thread-triggered event; không có
  autonomous world tick.

## 10. Non-goals của Phase 0/MVP

Không scaffold đầy đủ module rỗng, không nối provider thật, không build combat,
multiplayer, microservices, PostgreSQL/vector DB vận hành thật, TTS/hình ảnh,
mobile, marketplace, full WorldScheduler/NPCAgenda/WorldTick hoặc autonomous
rumor propagation.
