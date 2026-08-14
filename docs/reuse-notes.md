# Reuse inventory từ `novel-ai-trans`

Repository tham chiếu: `../novel-ai-trans`. Inventory này được lập ở Phase 0
bằng cách đọc source/docs/tests hiện có. Không copy toàn repository; mỗi mục
chỉ được port sau khi contract đích của interactive novel tồn tại.

## 1. Quy tắc port

1. Viết contract interactive-novel trước.
2. Port phần nhỏ nhất, đổi namespace và bỏ translation assumptions.
3. Giữ characterization test nếu hành vi hạ tầng quan trọng.
4. Viết test mới theo domain turn/branch/knowledge.
5. Ghi source path và thay đổi ở commit/ADR tương ứng.

## 2. Inventory theo module

| Target trong dự án mới | Source đã kiểm tra | Cách dùng |
|---|---|---|
| `pyproject.toml`, uv commands | `../novel-ai-trans/pyproject.toml`, `.python-version` | Tái sử dụng cấu trúc dependency groups, Ruff/Pyright/pytest và script pattern; pin lại dependency theo contract mới, không copy lock mù |
| CLI test/build/serve | `src/cli/test.py`, `src/cli/build.py`, `src/api/__main__.py` | Gần như trực tiếp về orchestration command; đổi label/project roots và thêm migrate |
| App factory/lifespan | `src/api/factory.py` | Tái sử dụng pattern `create_app`, lifespan, CORS, SPA fallback và exception registration; viết lại state/use-case registration |
| Error hierarchy | `src/application/errors.py`, `src/api/errors.py` | Tái sử dụng error envelope/mapping; đổi error code cho domain Guard/provider/branch và redact details |
| Health route/schema | `src/api/routes/health.py`, `src/api/schemas.py` | Pattern trực tiếp cho health; DTO mới không mang novel translation fields |
| API background job models | `src/api/background/models.py` | Tái sử dụng lifecycle dataclass, active/terminal status và public serialization; đổi scope từ novel sang turn/branch |
| Job conflict/registry | `src/api/background/registry.py` | Tái sử dụng lock/conflict pattern; policy mới là một active turn trên mỗi branch và global semaphore |
| Job manager/runner | `src/api/background/manager.py`, `runner.py`, `controllers.py` | Tái sử dụng coordination/cancellation/restart handling; không port child process translation worker |
| Event bus/SSE | `src/api/events.py`, `src/api/background/streaming.py`, `src/api/routes/jobs.py` | Tái sử dụng fan-out và fetch-based reconnect pattern; mở rộng vocabulary node/token/commit, Last-Event-ID và safe payload |
| Runtime path helpers | `src/paths.py` | Tái sử dụng path anchoring/validation idea; target `runtime/game.db`, `checkpoints.db`, exports, không có `translated/` |
| LLM base | `src/services/llm/base.py` | Tái sử dụng HTTP lifecycle, retry/error metadata/cancellation hooks; chuyển async và tách structured/text/stream/embed contract |
| Provider adapters | `src/services/llm/ollama.py`, `gemini.py`, `openrouter.py` | Tận dụng endpoint mapping/header/response parsing và mock fixtures; bỏ translation call types, thêm capabilities/role routing/privacy opt-in |
| Provider factory/fallback | `src/services/llm/factory.py`, `fallback.py` | Giữ factory/role snapshot/fallback pattern; fallback phải giữ schema, trace physical call và không lách policy |
| Cooperative cancellation | `src/services/llm/cancellation.py` | Tái sử dụng ý tưởng context-local safe point; port sang async cancellation token và stream cancellation |
| Prompt loader/cache | `src/prompts/__init__.py`, `src/services/generation/prompts.py`, `cache.py` | Tái sử dụng asset loader, context-local per-job cache và template hash; viết prompt registry/version/schema contract mới |
| LangGraph builder | `src/graph/builder.py` | Chỉ tái sử dụng graph builder/conditional edge/retry pattern; `TranslationState` và translation nodes bị loại |
| Graph state typing | `src/models/state.py` | Chỉ học cách bounded TypedDict/initializer; viết mới `TurnGraphState`, không port field/glossary/translation |
| Backend architecture tests | `tests/architecture/test_dependencies.py` | Tái sử dụng AST import-cycle/direction checks và frontend API ownership checks; cập nhật layer rules cho `graph → application contracts` |
| Provider/graph/API tests | `tests/services/test_llm.py`, `tests/graph/test_builder.py`, `tests/api/*` | Tái sử dụng test harness/mock style và characterization ideas; thay fixtures bằng typed claim/branch/turn contracts |
| Vue toolchain | `web/package.json`, `vite.config.ts`, `tsconfig.json` | Tái sử dụng Vue 3 + TypeScript + Vite + Pinia + Router scripts/alias; tạo shell theo màn hình world/play |
| Typed API client | `web/src/api/client.ts`, `types.ts` | Tái sử dụng request/error-envelope/auth-token và typed response pattern; viết endpoints world/playthrough/turn/branch/debug |
| SSE client | `web/src/api/sse.ts` | Tái sử dụng fetch stream parser, token header, AbortSignal; bổ sung Last-Event-ID/replay semantics |
| Pinia stores | `web/src/composables/jobs.ts`, `settings.ts` và các composables liên quan | Tái sử dụng `defineStore`, loading/error/refresh/race-sequence pattern; tạo turnJob/branch/playthrough/debug stores mới |
| Vue app/router shell | `web/src/main.ts`, `App.vue`, `router/index.ts` | Tái sử dụng app registration, auth-in-memory, lazy routes và theme shell; đổi navigation/screen semantics |

## 3. Chỉ kế thừa ý tưởng

Các module sau có pattern hữu ích nhưng không được copy contract/domain:

- `src/domain/entities.py`, `relationships.py`, `context.py` cho cách tách policy;
- `src/graph/nodes/context.py`, `quality.py`, `reviewer.py` cho node validation;
- `src/domain/quality.py` cho deterministic checklist;
- `src/services/glossary/memory.py` và learner cho provenance/history idea;
- `src/services/generation/selectors.py` cho validate → retry → final diagnostic;
- `src/application/config.py` cho config snapshot bất biến theo job.

Interactive novel phải thiết kế lại các phần này cho event, time, branch,
observation/belief, hidden state, typed claim và SceneSpec.

## 4. Không kế thừa

- `TranslationState`, chunking và translation nodes;
- glossary JSON làm memory chính hoặc relationship một nhãn;
- crawler/import EPUB/file workflow và `src/services/crawling/*`;
- `src/services/translation/*` và child worker tối ưu batch dịch;
- prompt/rule assets translation và assumptions về chapter output;
- cơ chế `novel` là đơn vị lock; target là branch/turn.

## 5. Điều chưa copy ở Phase 0

Phase này chỉ ghi inventory và source evidence. Chưa thêm code/runtime
dependency nào từ repository tham chiếu; việc port thực tế thuộc Phase 1, 5,
8, 10 và 11 theo contract tương ứng.
