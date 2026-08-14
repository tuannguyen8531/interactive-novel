# Báo cáo Phase 4 — Event log, snapshot và branching

## 1. Mục tiêu của Phase

Hoàn thiện lớp persistence canonical trước khi nối provider AI: commit lượt chơi
nguyên tử, optimistic revision, snapshot/replay có checksum, fork/regenerate và
truy vấn lịch sử branch không làm lẫn timeline.

## 2. Những gì đã thực hiện

- Mở rộng persistence contracts và application ports cho branch, turn, event,
  claim/fact/link, observation/belief/evidence, relationship/tension,
  thread/hook, snapshot và derived job.
- Thêm migration `0002_event_log_snapshot_branching.py` cùng SQLAlchemy models
  cho toàn bộ canonical tables, snapshot, outbox và derived jobs.
- Implement `SqlAlchemyCanonicalRepository.commit_turn()` với một transaction
  bao trùm turn, final narrative, canonical artifacts, current-state projections,
  branch head/revision và outbox/derived-job intents.
- Thêm optimistic `head_revision`, kiểm tra parent turn/world time, idempotency
  theo `turn_run_id` và lỗi stale-head ở application boundary.
- Thêm injected failure points để xác minh rollback tại từng bước commit.
- Thêm `BranchApplicationService` cho root branch, fork và regenerate. Branch
  con chỉ giữ ancestry metadata; không copy event/turn của ancestor.
- Thêm ancestry traversal và visible event/approved-patch queries; child chỉ
  thấy lịch sử ancestor đến fork turn, không thấy sibling hoặc parent future.
- Thêm JSON codec thuần domain cho `StatePatch` và `GameState`, snapshot SHA-256
  checksum, snapshot fallback khi thiếu/hỏng và `ReplayApplicationService`.
- Thêm derived-job outbox/reconciler, idempotency key và cập nhật trạng thái
  retry/failure độc lập với canonical turn.
- Thêm `InvariantReport` kiểm tra chain revision/head, parent chain, fork
  ancestry, clock consistency và snapshot checksum.
- Cập nhật migration smoke test và bổ sung persistence integration tests cho
  toàn bộ vertical slice của Phase 4.

## 3. File/module quan trọng

- `src/application/contracts/persistence.py`: records, canonical bundle,
  snapshot checksum, persistence errors và invariant report.
- `src/application/ports/persistence.py`: `CanonicalRepository` và UoW port.
- `src/application/services/branches.py`: root/fork/regenerate use cases.
- `src/application/services/canonical_turns.py`: transaction boundary và
  derived/snapshot/invariant use cases.
- `src/application/services/replay.py`, `src/domain/codec.py`: replay và
  serialization domain-owned.
- `src/services/persistence/models.py`, `canonical.py`, `uow.py`: SQLAlchemy
  mapping, canonical adapter và transaction wiring.
- `alembic/versions/0002_event_log_snapshot_branching.py`: schema migration.
- `tests/persistence/test_canonical_persistence.py`: atomicity, branching, replay, snapshot,
  checksum, idempotency và derived failure tests.

## 4. Quyết định triển khai đáng chú ý

- Domain không import SQLAlchemy hay framework; persistence chỉ phụ thuộc vào
  application contracts/ports.
- Branch inheritance được biểu diễn bằng `parent_branch_id`, `fork_turn_id` và
  parent-turn chain; không nhân bản canonical records.
- `head_revision` được tăng bằng một conditional update trong cùng transaction;
  stale base revision không được tạo turn hoặc làm đổi head.
- Snapshot là derived acceleration artifact. Checksum sai hoặc revision vượt
  head bị bỏ qua; replay quay về canonical approved-patch stream.
- Derived jobs/outbox chỉ lưu intent trong canonical transaction. Xử lý lỗi
  summary/snapshot/embedding diễn ra sau commit và chỉ đổi trạng thái job.
- Invariant verifier là read-only; không sửa chữa âm thầm dữ liệu canonical.

## 5. Tái sử dụng từ `novel-ai-trans`

Không copy toàn bộ repository và không phát hiện module cần kế thừa trực tiếp
cho Phase 4. Phase này tái sử dụng các persistence/application boundaries đã
được dựng ở Phase 2 và domain engine/StatePatch ở Phase 3 theo đúng chiến lược
kế thừa đã chốt trong plan.

## 6. Tests, lint và type-check

| Kiểm tra | Kết quả |
|---|---|
| `uv run test` | PASS — Ruff check, Ruff format, Pyright và pytest |
| `uv run pytest -q` | PASS — 53 tests |
| `uv run pytest -q tests/persistence/test_phase4.py` | PASS — 13 tests |
| `uv run pyright src tests` | PASS — 0 errors, 0 warnings |
| `uv run ruff check .` | PASS |
| Ruff format check thông qua `uv run test` | PASS |
| `uv run build` | PASS — Vue type-check và Vite production build |
| `git diff --check` | PASS |

## 7. Tiêu chí hoàn tất

- PASS — Replay cho kết quả giống current state. Đã kiểm tra replay từ patch
  stream, replay từ snapshot hợp lệ và fallback sau snapshot corruption.
- PASS — Hai branch không lẫn event/memory scope. Đã kiểm tra ancestry, child
  không thấy sibling hoặc parent future; mọi canonical record đều mang branch
  scope và artifact bundle đã được kiểm tra FK/branch isolation.
- PASS — Regenerate tạo branch mới mà không phá lịch sử. Đã kiểm tra root,
  child và sibling vẫn giữ turn/event history riêng.
- PASS — Inject lỗi tại từng bước commit đều rollback sạch. Đã kiểm tra 9 điểm:
  `head_revision`, `turn`, `events`, `knowledge`, `observations`,
  `relationships`, `narrative`, `outbox`, `head_update`.
- PASS — Summary/snapshot/embedding failure không rollback canonical turn. Đã
  kiểm tra snapshot checksum failure và derived job failure sau canonical commit;
  turn/head vẫn tồn tại, reconciler dựng lại job thiếu được.

## 8. Vấn đề, technical debt và blocker còn lại

- Replay hiện dùng `approved_patch` được lưu trên canonical turn làm change
  stream thực thi; bảng `events` vẫn là canonical audit record nhưng chưa tự
  chuyển ngược thành domain operation stream. Đây là boundary rõ ràng để mở rộng
  khi retrieval/context ở các phase sau cần đọc event/knowledge projections.
- Chưa có worker thực thi summary/embedding/snapshot trong Phase 4; hiện đã có
  outbox, job status, idempotency và reconciler để Phase 5+ nối vào.
- Không có blocker khiến Phase 4 không thể hoàn thành theo tiêu chí đã chốt.

## 9. Phase tiếp theo — chưa thực hiện

Phase 5 sẽ xây provider layer và các adapter Ollama/Gemini/OpenRouter theo
contract trung lập. Phase 4 không thực hiện provider, LangGraph, retrieval, API
turn job/SSE hoặc frontend vertical slice.

## 10. Git review và commit đề xuất

`git diff --check` đã PASS. Working tree chỉ chứa các thay đổi của Phase 4 và
report này; chưa chạy `git commit`, chưa push và không thay đổi lịch sử Git.

Commit message đề xuất:

```text
feat: implement Phase 4 event log snapshot and branching
```
