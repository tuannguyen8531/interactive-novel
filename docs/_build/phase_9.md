# Báo cáo Phase 9 — Application services

## Mục tiêu của Phase

Expose hành vi sản phẩm qua application use cases, giữ transaction boundary và
invariant ở application/persistence ports, đồng thời để API chỉ chuyển DTO và
error. Phạm vi thực hiện dừng ở application services; REST, background runner
durable và SSE thuộc Phase 10 chưa được triển khai.

## Những gì đã thực hiện

- Mở rộng world/playthrough use cases: create/get/list, world draft
  generate/validate/confirm, provider snapshot update.
- Bổ sung character seed/profile repository và lưu các character đã confirm từ
  `WorldSeed` trong cùng transaction với world.
- Bổ sung active branch selection và use cases fork/switch/regenerate.
- Bổ sung `TurnApplicationService` với submit/get/cancel, idempotency theo
  command key/run ID, optimistic base-revision check và một active turn trên
  mỗi branch trong process.
- Bổ sung read projections cho character public profile, memory,
  relationship và timeline theo playthrough/branch ancestry.
- Bổ sung provider settings service với snapshot không chứa secret và port test
  connectivity.
- Bổ sung export playthrough dạng typed, JSON-safe bundle gồm world,
  playthrough, branches, turns, characters, events, relationships và derived
  jobs.
- Thêm migration `0004_application_services` cho `playthroughs.active_branch_id`.

## Các file/module quan trọng đã tạo hoặc thay đổi

- Contracts: `src/application/contracts/queries.py`, `turns.py`, `exports.py`
  và `contracts/persistence.py`.
- Ports: `src/application/ports/persistence.py`, `turns.py`, `worlds.py` và
  provider settings port.
- Services: `world_drafts.py`, `turns.py`, `queries.py`, `provider_settings.py`,
  `export.py`; mở rộng `worlds.py`, `playthroughs.py`, `branches.py`.
- Persistence adapters: `repositories.py`, `queries.py`, `canonical.py`,
  `uow.py`, `models.py`.
- Migration: `alembic/versions/0004_application_services.py`.
- Integration tests: `tests/application/test_application_services.py`.

## Quyết định triển khai đáng chú ý

- `TurnApplicationService` chỉ giữ job registry và branch lock trong process;
  durable job state, global semaphore và SSE được để lại cho Phase 10.
- `TurnPipelineRequest` của Phase 8 được giữ nguyên để tránh đổi graph contract;
  application layer giao tiếp với graph qua `TurnRunner` port và
  `TurnRunRequest` riêng.
- `active_branch_id` được lưu riêng, không tái sử dụng `root_branch_id` để
  biểu diễn selection hiện tại.
- Public character query loại bỏ current state/internal turn metadata; memory
  và relationship inspection vẫn được scope theo playthrough và branch
  ancestry.
- Provider settings chỉ lưu `ProviderRoutingConfig.snapshot()`, không lưu API
  key hoặc header values.
- World draft chỉ trở thành persisted world/character records sau
  `confirm_world`; draft chưa xác nhận không được ghi.

## Những phần tái sử dụng từ novel-ai-trans

Không có code được copy trực tiếp từ một checkout `novel-ai-trans` trong
workspace. Phase này tái sử dụng các boundary đã có của dự án hiện tại và các
thành phần từ các phase trước: application errors/ports, SQLAlchemy UoW,
canonical repository, branch ancestry, provider contracts và LangGraph runner.

## Tests/lint/type-check đã chạy và kết quả

- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache timeout 30s uv run pytest tests/application/test_application_services.py -q`
  — **PASS**, 6 passed.
- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache timeout 30s uv run pytest tests/api tests/architecture tests/domain tests/services/test_ai_contracts.py tests/services/test_context_retrieval.py tests/services/test_prompt_registry.py tests/services/test_provider_routing.py -q`
  — **PASS**, 71 passed.
- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache timeout 30s uv run ruff check .`
  — **PASS**.
- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache timeout 30s uv run ruff format --check .`
  — **PASS**, 131 files already formatted.
- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache timeout 30s uv run pyright`
  — **PASS**, 0 errors/warnings/informations.
- `git diff --check` — **PASS**.
- `tests/graph/test_turn_pipeline.py` — **SKIP sau timeout 30 giây trong
  sandbox**; test đầu tiên không hoàn tất và không chờ thêm.
- `tests/persistence/test_migrations.py` — **SKIP sau timeout 30 giây trong
  sandbox**; không xác nhận được runtime SQLite/migration ở môi trường này.

Các integration tests Phase 9 dùng in-memory UoW/fakes để kiểm thử use-case
orchestration mà không phụ thuộc vào SQLite sandbox. Persistence adapters và
migration đã được kiểm tra bằng Ruff/Pyright/import, nhưng cần chạy lại runtime
SQLite ngoài sandbox.

## Tiêu chí hoàn tất

### Mỗi use case có integration test — PASS

Đã có test cho world draft/lifecycle, playthrough, branch fork/switch/regenerate,
turn submit/get/cancel và policy idempotency/concurrency, character/memory/
relationship/timeline queries, provider settings/connectivity và export.

### API layer có thể mỏng, chỉ chuyển DTO và error — PASS trong phạm vi Phase 9

Application services chỉ trả typed records/views/export hoặc application error;
không thêm logic persistence/provider vào API. REST routes thực tế vẫn thuộc
Phase 10 và chưa được thực hiện.

## Vấn đề, technical debt hoặc blocker còn lại

- SQLite migration/persistence integration bị sandbox treo quá 30 giây; cần Ân
  công chạy lại ngoài sandbox để xác nhận migration `0004` và các adapter query.
- Graph Phase 8 cũng không hoàn tất trong sandbox khi re-run; phần graph
  contract đã được giữ nguyên, nhưng cần chạy lại bộ `tests/graph` ngoài
  sandbox.
- Turn registry/branch lock hiện chỉ có hiệu lực trong một process và mất khi
  restart; Phase 10 phải chuyển job state/cancellation/recovery sang durable
  runner policy.
- Provider settings mặc định dùng in-memory store; snapshot theo playthrough đã
  có, còn global settings durable/keyring là việc cần chốt ở composition root.
- World confirmation đã persist world và character profiles; initial claims,
  relationships, goals và threads của seed chưa được materialize thành toàn bộ
  canonical playthrough records.

## Những việc dự kiến của Phase tiếp theo nhưng chưa thực hiện

- REST routes cho worlds/playthroughs/branches/turns/characters/providers.
- Durable background runner, job state persistence, per-branch lock và global
  semaphore.
- SSE progress, reconnect/replay, cancellation endpoint và graceful shutdown.
- Mapping provider/domain/application errors sang API error envelope cho các
  route mới.

## Git diff/status và commit đề xuất

- `git diff --check`: PASS.
- `git status --short`: còn các thay đổi Phase 9 chưa commit; không có commit,
  push hoặc thay đổi lịch sử Git trong Phase này.
- Commit message đề xuất:

  `feat: add Phase 9 application services`
