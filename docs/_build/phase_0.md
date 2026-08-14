# Báo cáo Phase 0 — Chốt kiến trúc và tiêu chí

- Ngày: 2026-08-13
- Nguồn tham chiếu chính: `docs/plan.md`
- Trạng thái: **Hoàn tất ở cấp contract/design của Phase 0**
- Commit: **chưa tạo**

## 1. Mục tiêu của Phase

Loại bỏ các quyết định mơ hồ trước khi scaffold: ownership của state/branch/
knowledge/transaction, typed mutation contract, content policy, logical AI
roles, off-screen boundary, acceptance scenarios và chiến lược kế thừa từ
`../novel-ai-trans`.

## 2. Những gì đã thực hiện

- Tạo 15 ADR accepted cho modular monolith, SQLite, event/current-state/
  snapshot, LangGraph boundary, provider adapters, relationships, typed
  knowledge, visibility, logical-vs-physical calls, canonical-vs-derived,
  off-screen, content policy, branch, relationship scale và in-world clock.
- Chốt dependency direction, aggregate ownership, canonical transaction và
  bounded `TurnGraphState` contract trong architecture/domain model.
- Chốt glossary và typed contracts cho World, Playthrough, Branch, Turn,
  Event, KnowledgeClaim, CanonFact, Observation, Belief, StatePatch,
  SceneSpec, Relationship, Tension, Thread và derived artifacts.
- Chốt state machine cho Turn, background Job, Branch và Consent; content
  decision có `allow`/`downgrade`/`deny` cùng reason codes.
- Chuẩn hóa ContentPolicy với rating `teen_14_plus`, `mature_16_plus`,
  `adult_18_plus`, topic tags, violence ceiling, player tightening,
  participant-age gate, consent và timeskip semantics.
- Lập reuse inventory theo module/file với phân loại: port gần như trực tiếp,
  điều chỉnh đáng kể, chỉ kế thừa ý tưởng và không kế thừa.
- Tạo 11 acceptance scenarios, 7 typed-claim cases, 13 content-policy cases
  và 3 reference-matrix entries dưới `tests/fixtures/scenarios/`.

## 3. File/module quan trọng đã tạo

- Kiến trúc/domain: `docs/architecture.md`, `docs/domain-model.md`,
  `docs/state-machines.md`, `docs/content-policy.md`.
- ADR: `docs/adr/README.md` và `docs/adr/0001` đến `0015`.
- Kế thừa: `docs/reuse-notes.md`.
- Fixtures: `tests/fixtures/scenarios/README.md`,
  `core_acceptance.json`, `claim_contracts.json`, `content_policy.json`,
  `reference_matrix.json`.
- Báo cáo: `docs/_build/phase_0.md`.

Không tạo `src/`, `web/`, migration, provider code, LangGraph node hoặc domain
implementation; đó là phạm vi của các Phase sau.

## 4. Quyết định triển khai đáng chú ý

- `game.db` và `checkpoints.db` tách biệt; checkpoint không phải save game.
- Canonical turn commit nguyên tử; summary, snapshot, embedding, index,
  consolidation và analytics là derived jobs không được rollback turn.
- Mọi authoritative mutation phải là typed claim hoặc typed state operation;
  prose không có quyền tạo canon.
- Retrieval hard-filter theo playthrough, branch ancestry/fork boundary,
  world time và owner trước semantic/vector ranking.
- Năm logical AI roles không bị đồng nhất với năm physical model calls; fuse/
  split phải giữ artifact và validator riêng, Guard luôn chạy.
- Relationship là directed vector; `familiarity` do engine suy ra, jealousy là
  tension ba ngôi, không phải scalar.
- Branch regenerate tạo branch mới; sibling/future không leak; undo chỉ move
  head khi không có descendant sau điểm undo.
- Off-screen chỉ materialize ScheduledEvent, due NarrativeThread hoặc diễn biến
  cần cho scene và đã qua Guard; không autonomous world tick.
- Player boundary chỉ giữ nguyên hoặc siết World policy; explicit adult cần mọi
  participant từ 18 tuổi, world/player opt-in và consent hợp lệ.

## 5. Phần tái sử dụng từ `novel-ai-trans`

Inventory đã ghi source path cụ thể. Các pattern được chọn gồm:

- uv/tooling command shape, Ruff/Pyright/pytest setup và app factory/error
  envelope;
- background job lifecycle, per-target conflict, event bus, SSE fan-out và
  restart/cancellation handling;
- HTTP provider lifecycle, retry/backoff, response mapping, fallback và
  cooperative cancellation;
- prompt asset loader/cache, LangGraph builder/conditional-edge pattern;
- Vue 3 + TypeScript + Vite + Pinia + Router shell, typed API client và
  fetch-based SSE client;
- AST architecture-test pattern.

Không tái sử dụng `TranslationState`, translation nodes/chunking, glossary làm
memory chính, crawler/EPUB workflow, translation child worker hay relationship
translation một nhãn.

## 6. Tests/lint/type-check đã chạy

| Kiểm tra | Kết quả |
|---|---|
| `python3 -m json.tool` trên 4 JSON fixture | PASS |
| `jq` uniqueness/completeness/decision enum/preset/reference checks | PASS |
| `git diff --no-index --check` trên output Phase 0 | PASS |
| Audit tồn tại 15 ADR + toàn bộ output/fixture bắt buộc | PASS |
| `uv run test` | BLOCKED: skeleton chưa có `src/interactive_novel/__init__.py`; đây là việc Phase 1 |
| `uv run --no-sync ruff check .` | BLOCKED: Ruff chưa được cài trong skeleton |
| `uv run --no-sync pyright` | BLOCKED: Pyright chưa được cài trong skeleton |
| `uv run --no-sync pytest -q` | BLOCKED: Pytest chưa được cài và chưa có test package |

Lần đầu `uv` ghi cache vào vùng read-only nên bị lỗi môi trường; đã rerun với
`UV_CACHE_DIR=/tmp/interactive-novel-uv-cache`. `uv.lock` sinh ra trong lượt
thử đã được loại bỏ vì Phase 0 không scaffold dependency lock. Không có test
model/provider thật nào được gọi.

## 7. Tiêu chí hoàn tất

| Tiêu chí trong `plan.md` | Kết quả | Bằng chứng |
|---|---|---|
| Không còn câu hỏi mở về ownership state, branch, knowledge, transaction | PASS | `docs/architecture.md`, `docs/domain-model.md`, ADR 0001/0003/0008/0010/0013 |
| AI fact/state mutation ánh xạ typed claim/operation | PASS | ADR 0007, `claim_contracts.json`, StatePatch contract |
| Khóa năm logical roles không bắt buộc năm calls | PASS | ADR 0009, architecture section 7 |
| Khóa MVP không autonomous off-screen world tick | PASS | ADR 0011, `offscreen-boundary` scenario |
| ContentPolicy enforce được 14+/16+/18+, consent, violence bằng deterministic contract/tests | PASS ở cấp Phase 0 | Schema, evaluation order, reason codes, consent state machine và 13 table-driven vectors; executable Guard tests thuộc Phase 3 khi domain engine tồn tại |
| Mỗi acceptance scenario có expected invariant | PASS | 11 scenario trong `core_acceptance.json`, gồm narrative degeneracy 30 turn |

## 8. Vấn đề, technical debt và blocker còn lại

- Chưa có runtime Guard để thực thi fixture; Phase 3 phải parameterize các
  vector thành unit/property tests và giữ hard gates bằng 0.
- Reference matrix còn `to_be_filled` cho model/hardware/network; Phase 3 phải
  đo baseline thật trước khi khóa gate M3/M4.
- Ruff, Pyright, Pytest, package `src/` và frontend chưa tồn tại; đây là trạng
  thái đúng của skeleton trước Phase 1, không phải blocker kiến trúc.
- `docs/_build/` đang bị `.gitignore` bỏ qua; report vẫn tồn tại để review nhưng
  `git status --short` không liệt kê như file untracked.

Không phát hiện mâu thuẫn kiến trúc hoặc blocker cần đổi plan. Không thực hiện
Phase 1.

## 9. Việc dự kiến của Phase tiếp theo nhưng chưa thực hiện

Phase 1 sẽ scaffold uv/pyproject dependency, Ruff/Pyright/pytest, package
`src`, FastAPI app factory/health/error envelope, CLI serve/test/migrate, Vue 3
shell, typed API/SSE client và architecture tests. Chưa có hạng mục nào trong
danh sách này được triển khai ở Phase 0.

## 10. Git review

- `git diff --stat`: không có tracked diff vì repository chưa có commit và các
  file hiện tại đều đang untracked.
- `git diff --check`: sạch.
- `git status --short`: chỉ gồm các file skeleton/docs/fixtures dự kiến;
  không có `uv.lock` sinh dư hoặc file runtime ngoài scope.
- Không chạy `git add`, `git commit`, `git push` hay thay đổi lịch sử Git.

## 11. Commit message đề xuất

```text
docs: establish Phase 0 architecture and acceptance contracts
```
