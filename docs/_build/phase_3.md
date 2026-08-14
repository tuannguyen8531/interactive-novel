# Báo cáo Phase 3 — Pure domain engine

## 1. Mục tiêu của Phase

Theo `docs/plan.md`, Phase 3 phải cung cấp domain engine thuần, mô phỏng được
state patch hoàn toàn in-memory, không cần LLM, framework hay persistence.
Phase này phải giữ các invariant về clock, character state, directed
relationship, content/consent, typed knowledge, narrative thread và quyền
authoritative của `StatePatch` qua deterministic Guard.

## 2. Những gì đã thực hiện

- Thêm value objects `TimeRange`, `Provenance`, clock primitives và
  `ClockPolicy`; clock chỉ tiến về phía trước theo integer minutes.
- Thêm `CharacterProfile`, `CharacterState`, `Character` và
  `PsychologicalState`; profile ổn định, state thay đổi bằng replacement và các
  trường tâm lý được giữ trong range.
- Thêm directed `RelationshipVector`, policy riêng cho tám dimension, audit
  `RelationshipChange` và projection label không authoritative.
- Thêm `derive_familiarity()` engine-derived; Guard/operation từ chối direct
  familiarity mutation.
- Thêm `ContentPolicy`, player override chỉ có thể tighten policy, content tags,
  rating/age gate, violence ceiling, consent state machine và deterministic
  `PolicyDecision`. Toàn bộ fixture `content_policy.json` được kiểm chứng.
- Thêm typed `KnowledgeClaim`, `CanonFact`, `ClaimLink`, versioned
  `PredicateRegistry` và SHA-256 normalized fingerprint ổn định với mapping key
  order khác nhau.
- Thêm immutable `Event`, `Observation`, `Belief`, `Evidence` với hard checks
  cho owner, branch, chronology và future leakage.
- Thêm `NarrativeThread`, `NarrativeHook` và lifecycle transition rules.
- Định nghĩa typed `StateOperation`/`StatePatch`, gồm clock, character,
  psychology, relationship, claims/canon/links, event/evidence/observation/
  belief, thread/hook và consent operations.
- Thêm `GameState` in-memory và `DomainGuard` sequential shadow validation:
  patch branch/base time, typed-operation authority, references, ranges,
  provenance, branch ancestry, valid time, owner/evidence authorization,
  transition lifecycle và content policy.
- Thêm `DomainEngine` với injected RNG/clock factory, immutable-style
  apply-to-copy, before/after snapshots, revert và replay; không ghi database
  hay gọi LLM.
- Bổ sung Hypothesis vào dev dependencies và property tests cho relationship
  ranges và referential integrity.

## 3. File/module quan trọng đã tạo hoặc thay đổi

Domain modules mới:

- `src/domain/values.py`, `errors.py`, `clock.py`.
- `src/domain/characters.py`, `psychology.py`, `relationships.py`.
- `src/domain/content.py`, `knowledge.py`, `events.py`, `narrative.py`.
- `src/domain/patch.py`, `state.py`, `guard.py`, `engine.py`.
- `src/domain/__init__.py` export public domain contract.

Tests và dependency:

- `tests/domain/test_entities.py`.
- `tests/domain/test_relationships.py`.
- `tests/domain/test_content_policy.py`.
- `tests/domain/test_knowledge.py`.
- `tests/domain/test_engine.py`.
- `pyproject.toml`, `uv.lock` thêm Hypothesis/sortedcontainers.
- Báo cáo này tại `docs/_build/phase_3.md`.

## 4. Quyết định triển khai đáng chú ý

- Domain chỉ import Python standard library và module trong `src.domain`;
  không có FastAPI, SQLAlchemy, Pydantic, LangGraph, provider hay filesystem
  dependency.
- Guard không mutate `GameState`: nó dựng các collection shadow theo thứ tự
  operation để hỗ trợ add-then-reference trong cùng patch, rồi Engine mới apply
  vào deep copy sau khi toàn bộ patch pass.
- `StateOperation` là marker authority duy nhất. Dict/prose/object tùy ý trong
  `StatePatch.operations` bị từ chối với `untyped_operation`.
- Relationship là directed edge và mỗi dimension dùng policy/range riêng;
  familiarity không nhận delta trực tiếp mà chỉ có thể được suy ra từ lịch sử.
- Content evaluation dừng theo thứ tự deterministic: schema/tag, tuổi tại
  `SceneSpec.world_time`, mixed adult/minor, explicit age, violence, excluded
  topic, rating/opt-in/consent. Timeskip không sửa decision lịch sử.
- Claim, event, observation, evidence và belief đều bị hard-filter bởi
  playthrough/branch/time/owner trước khi được authoritative; observation và
  belief không thể tự assert canon.
- Apply/revert/replay hiện là in-memory snapshots. Event log, snapshot
  persistence, branch persistence và canonical commit transaction được giữ cho
  Phase 4 theo plan/ADR; không mở rộng vào Phase 3.

## 5. Những phần tái sử dụng từ novel-ai-trans

- Không copy domain hoặc translation repository vào Phase 3. Domain engine,
  claim model, relationship model, content policy và Guard được viết mới theo
  ADR/domain contract của interactive novel.
- Chỉ tiếp tục dùng các convention/tooling đã được port từ các phase trước
  (Ruff, Pyright, pytest CLI và architecture-test pattern). Không có module
  source nào từ `novel-ai-trans` được copy trực tiếp trong Phase này.

## 6. Tests, lint và type-check

| Kiểm tra | Kết quả |
|---|---|
| `uv run test` | PASS — Ruff check, Ruff format, Pyright và toàn bộ pytest |
| `uv run pytest -q tests/domain` | PASS — 30 tests, gồm fixture tests và Hypothesis properties |
| `uv run build` | PASS — frontend `vue-tsc` và Vite production build |
| `git diff --check` | PASS |
| Domain dependency architecture test | PASS trong `uv run test`; domain không import framework/infrastructure |

## 7. Tiêu chí hoàn tất

- PASS — Fixture action tạo `StatePatch`, qua Guard và apply hoàn toàn
  in-memory; test kiểm tra clock, character state, psychology, relationship,
  canon fact, revert và replay.
- PASS — Invalid transition bị từ chối bằng code rõ như
  `invalid_thread_transition`, `invalid_consent_transition`,
  `branch_scope_mismatch` và `stale_patch_base_time`.
- PASS — Untyped mutation/prose không thể trở thành authoritative; Guard trả
  `untyped_operation`.
- PASS — Claim/evidence/observation/belief sai owner, branch hoặc time bị Guard
  từ chối; có coverage cho sibling branch, future claim/evidence,
  non-witness observation và owner mismatch.
- PASS — Scene sai age/rating/consent/violence/excluded topic trả decision/code
  deterministic theo fixture, không phụ thuộc LLM.
- PASS — `src.domain` không import framework/infrastructure; architecture test
  và Pyright/Ruff đều xanh.
- PASS — Property tests cho relationship range và referential integrity xanh,
  gồm Hypothesis-generated cases.

## 8. Vấn đề, technical debt và blocker còn lại

- Không có blocker làm chặn hoàn tất Phase 3.
- `GameState` hiện là aggregate in-memory; chưa có event store, snapshot,
  optimistic revision, branch ancestry persistence hoặc canonical transaction.
  Đây là phạm vi Phase 4, không phải thiếu sót cần kéo ngược vào Phase 3.
- Content policy nhận participant ages trực tiếp trong `SceneSpec` hoặc qua
  `SceneSpec.from_profiles`; application/planner integration để tạo SceneSpec
  từ canonical state sẽ làm ở phase sau.
- `DomainRuntime` đã nhận RNG và clock factory, nhưng Phase 3 chưa có simulator
  planner sử dụng randomness; đó là boundary sẵn sàng cho các phase orchestration.

## 9. Những việc dự kiến của Phase tiếp theo nhưng CHƯA thực hiện

Phase 4 — Event log, snapshot và branching chưa được thực hiện. Chưa tạo event
log persistence, current-state projection, snapshot checkpoint, branch fork/
ancestry query, revision conflict hay regenerate branch. Cũng chưa tích hợp
domain engine vào application service/API/graph.

## 10. Git diff, status và commit đề xuất

- Phase 2 đã được commit trước khi bắt đầu Phase 3: `d675e55` —
  `feat: add Phase 2 persistence foundation`.
- Phase 3 chưa commit, chưa push và không thay đổi lịch sử Git.
- `git diff --check`: PASS.
- Working tree gồm `src/domain/*`, `tests/domain/*`, `pyproject.toml` và
  `uv.lock`; báo cáo dưới `docs/_build` cần được force-add nếu muốn đưa vào
  commit do thư mục build bị ignore.
- Commit message đề xuất: `feat: implement Phase 3 pure domain engine`.
