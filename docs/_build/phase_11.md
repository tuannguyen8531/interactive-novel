# Báo cáo Phase 11 — Frontend vertical slice

## 1. Mục tiêu của Phase

Xây dựng một vertical slice frontend có thể chơi được với world fixture, bao
gồm Library/Home, Play Screen, transcript, free-action input, tiến độ job/SSE,
trạng thái lỗi/retry/cancel, branch timeline, character panel, provider
settings và Developer Inspector. Phạm vi được giữ ở client Vue 3/TypeScript;
không mở rộng sang AI World Builder của Phase 12.

## 2. Những gì đã thực hiện

- Mở rộng typed API client cho world, playthrough, branch, export, character,
  memory, relationship, timeline, turn/job, provider settings và connectivity.
- Hoàn thiện fetch-based SSE client:
  - gửi `Authorization` và `Last-Event-ID`;
  - parse nhiều event trong một chunk;
  - hỗ trợ đóng stream idempotent;
  - giữ vocabulary/event payload theo contract Phase 10.
- Tạo frontend fixture deterministic `Moonlight Academy`:
  - 3 character public profiles;
  - 10 narrative beats và free-action input;
  - progress events `context_started`, `writer_token`, `completed`;
  - cancel/failed/retry state;
  - localStorage persistence cho transcript, head, branch và world clock.
- Tạo các Pinia stores theo frontend architecture trong `plan.md`:
  - `libraryStore`;
  - `worldBuilderStore` (contract tối thiểu, UI World Builder để Phase 12);
  - `playthroughStore`;
  - `turnJobStore`;
  - `branchStore`;
  - `characterStore`;
  - `settingsStore`;
  - `providerStore`;
  - `debugStore`.
- Xây dựng router và màn hình:
  - Home/Library;
  - Play Screen với scene header, transcript, action input, progress và
    retry/cancel;
  - branch timeline tối thiểu với fork/switch;
  - character presence/profile panel;
  - provider settings và connectivity test;
  - Developer Inspector chỉ bật trong dev mode.
- Thêm design tokens/CSS nền tảng trực tiếp trong Vue shell, không thêm UI
  framework lớn.
- Thêm README frontend với lệnh chạy và hướng dẫn fixture/API base URL.

## 3. File/module quan trọng đã tạo hoặc thay đổi

- API contracts/transport:
  - `web/src/api/types.ts`;
  - `web/src/api/client.ts`;
  - `web/src/api/sse.ts`;
  - `web/src/api/sse.test.ts`.
- Fixture:
  - `web/src/fixtures/fixture.ts`.
- Stores:
  - `web/src/stores/library.ts`;
  - `web/src/stores/playthrough.ts`;
  - `web/src/stores/turnJob.ts`;
  - `web/src/stores/branch.ts`;
  - `web/src/stores/character.ts`;
  - `web/src/stores/provider.ts`;
  - `web/src/stores/settings.ts`;
  - `web/src/stores/debug.ts`;
  - `web/src/stores/worldBuilder.ts`;
  - `web/src/stores/verticalSlice.test.ts`.
- UI/app shell:
  - `web/src/App.vue`;
  - `web/src/router/index.ts`;
  - `web/src/views/HomeView.vue`;
  - `web/src/views/PlayView.vue`;
  - `web/src/views/SettingsView.vue`;
  - `web/src/views/InspectorView.vue`;
  - `web/README.md`.

## 4. Các quyết định triển khai đáng chú ý

- Fixture là adapter dev/test local-only, không thay thế API server. Khi mở
  playthrough thật, `PlaythroughExport` từ backend là nguồn sự thật; fixture
  chỉ cho phép kiểm thử UI khi Ollama/API provider chưa sẵn sàng.
- Transcript của branch được dựng từ branch ancestry và `fork_turn_id`; turn
  kế thừa chỉ xuất hiện đến fork boundary, turn local giữ revision riêng của
  branch.
- Fixture dùng localStorage key `interactive-novel.fixture.v1` để reload giữ
  đúng transcript/head/branch/world clock.
- `turnJobStore` dùng cùng một state machine cho API SSE và fixture events;
  terminal fixture chỉ xuất hiện sau khi callback commit turn hoàn tất.
- Provider settings chỉ hiển thị metadata an toàn; UI không nhận hoặc lưu
  API key inline.
- Developer Inspector được gate bởi `import.meta.env.DEV` và chỉ chứa scoped
  projection metadata/job event summary; không đưa inspector data vào
  player-facing transcript.
- Không thêm dependency mới. Playwright chưa có trong `web/node_modules`, vì
  vậy không tự tải package trong sandbox.
- Không copy trực tiếp code từ `novel-ai-trans`; chỉ kế thừa strategy/boundary
  typed API, SSE và Pinia đã được ghi trong reuse inventory và Phase 1.

## 5. Tests/lint/type-check đã chạy và kết quả

- `timeout 30s npm run build` trong `web/` — **PASS**:
  `vue-tsc --noEmit` và Vite production build đều thành công.
- `timeout 30s npm run test:unit` trong `web/` — **PASS**, 3 test files và 8
  tests:
  - app health store;
  - SSE event ordering và `Last-Event-ID`;
  - fixture 10-turn flow;
  - branch fork/switch isolation;
  - cancellation;
  - failed/retry state;
  - fixture serialize/restore.
- `git diff --check` — **PASS**.
- Frontend lint riêng chưa có script/dependency trong skeleton; `vue-tsc` và
  production build là kiểm tra type/static chính của frontend hiện tại.
- `npm run dev -- --host 127.0.0.1` — **BLOCKED bởi sandbox**: Vite trả
  `listen EPERM: operation not permitted 127.0.0.1:5173`, không phải timeout.
  Tiểu nữ không chờ quá 30 giây và không thử lặp lại.
- Playwright E2E happy/error path — **CHƯA CHẠY** vì package không có sẵn và
  dev server không được phép bind cổng trong sandbox. Không tải package mới.
- Backend lint/type-check/test không chạy lại trong Phase 11 vì Phase này chỉ
  thay đổi frontend; kết quả backend gần nhất được ghi ở báo cáo Phase 10.

## 6. Tiêu chí hoàn tất

| Tiêu chí trong `plan.md` | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| Người dùng chơi được fixture world 10 lượt qua browser | **PASS về implementation; cần xác nhận runtime browser** | Store vertical-slice test chạy đủ 10 lượt, production build thành công và UI có route `/play/fixture-playthrough`. Browser manual/E2E chưa chạy do Vite bind `EPERM` và thiếu Playwright. |
| Reload giữ đúng transcript/head | **PASS về implementation; cần xác nhận runtime browser** | localStorage persistence + serialize/restore unit test; browser reload thực tế chưa chạy trong sandbox. |
| Có thể fork và tiếp tục ở hai nhánh | **PASS** | Store test xác nhận root/child transcript tách biệt, switch branch và tiếp tục child branch; UI có branch timeline/fork/switch controls. |

Phase 11 đã hoàn thành phần code và verification không phụ thuộc network;
hai mục đầu có giới hạn xác nhận runtime browser do môi trường sandbox nêu
trên. Ân công cần chạy manual browser/Playwright ngoài sandbox để đóng dấu
hoàn tất runtime.

## 7. Vấn đề, technical debt hoặc blocker còn lại

- Blocker môi trường: sandbox không cho Vite bind `127.0.0.1:5173`; chưa thể
  chạy click-through browser tại đây.
- Playwright chưa được cài; E2E happy/error path cần được bổ sung/chạy ở môi
  trường có browser và dependency tương ứng.
- Backend Phase 10 vẫn dùng `GameState.empty(...)` khi nhận turn API; hydrate
  canonical state đầy đủ là technical debt backend đã ghi nhận ở Phase 10,
  có thể ảnh hưởng API playthrough thật dù fixture client hoạt động độc lập.
- SSE history của backend vẫn bounded in-memory theo Phase 10; reload frontend
  dựa vào export/job state, không giả định token replay sau process restart.
- Provider settings backend mặc định có thể trả `null` vì store hiện tại là
  in-memory; UI đã có empty/error state nhưng chưa có durable global settings.

## 8. Những việc dự kiến của Phase tiếp theo nhưng CHƯA thực hiện

Phase 12 — AI World Builder — chưa thực hiện. Chưa làm:

- New World prompt flow;
- WorldSeed draft generation;
- deterministic/semantic validation UI;
- draft editing và content-warning review;
- confirm atomic World + characters + relations + hooks;
- opening scene từ world do người dùng tạo.

## 9. Git diff/status và commit message đề xuất

- `git diff --check`: **PASS**.
- `git status --short`: còn các thay đổi frontend của Phase 11 chưa commit;
  `docs/_build/phase_11.md` nằm dưới thư mục ignored theo repository policy.
- Không chạy `git commit`, không push và không thay đổi lịch sử Git trong Phase
  11.
- Commit message đề xuất:

  `feat: add Phase 11 frontend vertical slice`
