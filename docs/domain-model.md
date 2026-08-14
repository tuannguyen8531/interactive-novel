# Domain model và glossary

Đây là contract domain trước khi viết implementation. Tên field dưới đây là
định hướng canonical model; DTO/API có thể đổi cách trình bày nhưng không được
đổi nghĩa hoặc bỏ provenance/scope.

## 1. Quy ước chung

- Domain ID là UUID dạng TEXT, không dùng SQLite rowid làm identity.
- Timestamp audit là UTC; thời gian trong truyện là `InWorldClock` độc lập.
- Mọi record có `schema_version` khi schema có khả năng tiến hóa.
- Branch/time/owner là scope bắt buộc cho query có nguy cơ lộ knowledge.
- `provenance` tối thiểu gồm source type, source ID, turn/run ID và prompt/model
  metadata nếu nguồn là AI.

## 2. Glossary

| Thuật ngữ | Nghĩa chuẩn |
|---|---|
| World | Vũ trụ tái sử dụng: premise, canon, locations, characters seed, policy |
| Playthrough | Một lần chơi của một World, có player, clock, RNG và root branch |
| Branch | Một timeline có parent/fork/head độc lập |
| Revision | Số phiên bản canonical của một branch head |
| Turn | Một action/input và kết quả được commit nguyên tử |
| Event | Điều thực sự đã xảy ra, bất biến sau commit |
| Canon | Tập điều engine xác định là đúng trong thế giới |
| KnowledgeClaim | Proposition typed có subject/predicate/object/value và scope |
| CanonFact | Assertion có thẩm quyền lên một KnowledgeClaim |
| Observation | Proposition một observer tiếp nhận từ event/source |
| Belief | Proposition một character tin, có thể sai |
| ClaimLink | Quan hệ evidence giữa các claim |
| StatePatch | Danh sách typed state operations trước Guard |
| SceneSpec | Phần outcome/chi tiết được Guard duyệt cho Writer biểu đạt |
| NarrativeThread | Tuyến xung đột/mục tiêu đang tiến triển |
| NarrativeHook | Setup/payoff cue gắn với event/thread |
| Derived artifact | Dữ liệu có thể xóa và rebuild 100% từ canonical data |
| Logical role | Contract AI như Planner hoặc Writer |
| Physical call | Một request model thực tế, có thể phục vụ nhiều role |
| World time | Thời gian trong truyện theo integer minutes từ world epoch |
| Consent | Quyền đồng thuận cho activity cụ thể; không phải relationship score |
| Content boundary | Giới hạn chủ đề/rating do World hoặc Player cấu hình |

## 3. Aggregate và identity

### World

World chứa premise, genre/tone, canon rules, locations, character templates,
content policy, initial claims, initial threads/hooks và schema version. World
không chứa current state của playthrough.

### Playthrough

Playthrough tham chiếu World, có player character, root branch, provider/config
snapshot, `InWorldClock`, RNG seed/state và lifecycle active/completed/archived.

### Branch

Branch có parent, fork turn/depth, head turn, head revision và lifecycle
`active/abandoned`. Canonical query resolve ancestor đến fork point inclusive rồi
mới áp local events; sibling/future sau fork không thuộc branch.

### Turn

Turn giữ raw input, normalized input, base revision, parent turn, status
`queued/running/completed/failed/cancelled`, final narrative, approved patch,
config/prompt versions, world-time interval, token/timing metadata và
`turn_run_id`. `committing` là internal/SSE phase; status chỉ chuyển
`completed` sau transaction thành công.

## 4. Character và tâm lý

`CharacterProfile` ổn định: identity/aliases, age anchor, role/background,
appearance/voice, traits, values, boundaries, long-term goals, likes/dislikes,
initial secrets.

`CharacterState` thay đổi: location, physical condition, emotional state,
short-term goals, attention target, stress/fatigue, inventory reference và last
active turn. Không sửa profile để lưu cảm xúc tạm thời.

`PsychologicalState` tối thiểu có valence, arousal, dominance/control, stress,
fatigue, needs, active goals, appraisals và suppressed emotions. Simulator chỉ
được dùng beliefs/relations/context mà role đó được authorize.

Player có profile/state như một entity bình thường, nhưng player intent là
nguồn chính cho hành động và cảm xúc được biểu lộ; AI không tự ghi hidden
thought trái input. Hidden player state chỉ được tạo bởi typed operation có
policy rõ ràng.

## 5. Event, claim, observation và belief

### Event

Event bất biến có type, world time, location, actors, targets, witnesses,
structured payload, salience, emotional intensity, cause references, turn và
branch. Off-screen event có cùng contract, không có schema riêng lỏng hơn.

### KnowledgeClaim và CanonFact

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

Predicate registry school-romance MVP hữu hạn và versioned:

| Predicate | Subject/object hoặc value | Mục đích |
|---|---|---|
| `located_at` | character/location | Canon vị trí trong world time |
| `age_is` | character/integer | Tuổi tại valid time |
| `romantic_interest` | character/character | Tình cảm có hướng |
| `commitment_status` | character/character/enum | Commitment event/state |
| `goal_active` | character/goal ID | Mục tiêu đang theo đuổi |
| `secret_exists` | owner/secret ID | Secret typed, không phải text tự do |
| `item_held` | character/item ID | Vật đang được giữ |
| `physical_condition` | character/enum/value | Tình trạng thể chất |
| `public_fact` | entity/typed value | Fact công khai được authorize |
| `event_participation` | character/event ID | Actor/witness participation |

Các claim mới phải đăng ký schema và migration. Relationship delta, clock
advance, thread transition và character state delta là typed `StateOperation`
riêng; không dùng predicate registry để né policy.

Fingerprint chuẩn hóa subject/predicate/object-or-value/polarity/qualifiers/
valid-time/branch-scope với key ordering deterministic. Claim ID khác fact
identity.

### Observation

Observation gồm observer, source event/information, observed claim, method
(`saw/heard/told/inferred`), confidence, distortion, timestamp và claim links.

### Belief

Belief gồm believer, claimed proposition, stance (`supports/rejects/uncertain`),
confidence, evidence/counter-evidence, source reliability và created/updated
turn. Belief không thể tự assert CanonFact.

## 6. StatePatch và authority

`StatePatch` là danh sách operation typed, ví dụ:

- `AdvanceClock(duration_minutes)`;
- `SetCharacterLocation(character_id, location_id)`;
- `SetCharacterCondition(character_id, condition)`;
- `UpdatePsychology(character_id, typed_delta)`;
- `ApplyRelationshipDelta(source, target, dimension, proposed_delta, cause)`;
- `AddKnowledgeClaim(claim)` / `AssertCanonFact(claim_id)`;
- `AddObservation(observation)` / `UpdateBelief(belief)`;
- `TransitionThread(thread_id, status, progress_delta)`;
- `MaterializeScheduledEvent(event)`.

Simulator chỉ đề xuất operation. Guard kiểm tra IDs, range, branch/time,
authorization, content policy, idempotency và state transition. Canonical Record
Builder chỉ nhận patch đã được Guard duyệt; prose không phải input authority.

## 7. Quan hệ và tension

Relationship là directed edge với các dimension trong
`docs/adr/0014-relationship-scale.md`. Mọi change log before/proposed/validated/
after, cause event, reason, LLM run và prompt version. Labels `friend`, `crush`,
`lover`, `rival` là derived projection; `lover` cần commitment evidence.

`EmotionalTension` dùng observer/rival/focus/trigger/intensity/appraisal/decay/
visibility để biểu diễn jealousy và hiểu lầm ba ngôi.

## 8. Narrative thread/hook

Thread có premise, participants, status (`seeded`, `active`, `escalating`,
`resolved`, `abandoned`), stakes, progress, urgency, last advanced turn và resolution
conditions. Hook có setup, expected payoff window, related memory/event,
visibility và status. Memory retrieval không thay thread management.

## 9. Clock, RNG và policy visibility

`InWorldClock` dùng integer minutes từ epoch; mỗi turn có start/duration/end,
duration do Planner đề xuất và Guard clamp. Branch kế thừa clock tại fork rồi
tiến độc lập. UTC timestamp chỉ là audit.

RNG được seed và lưu theo playthrough/branch; chỉ rule/check có khai báo mới
được dùng. Replay phải dùng lại RNG state.

Player mode chỉ thấy transcript, scene state được phép và relationship label mơ
hồ; developer mode mới inspect claims, beliefs, evidence, vectors, hidden goals,
retrieval trace và LLM metadata.

## 10. Source-of-truth rules

- CanonFact/current state/event là authority.
- Observation/belief là perspective-specific authority về việc nhân vật đã
  tiếp nhận hoặc tin gì, không phải truth của world.
- Narrative summary, embedding, retrieval index và snapshot là derived.
- LangGraph checkpoint là execution artifact.
- Khi derived thiếu/stale, read path fallback canonical state/raw event.
