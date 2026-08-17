# Báo cáo Phase 5 — Provider-neutral LLM layer

## 1. Mục tiêu của Phase

Xây dựng lớp provider trung lập để application có thể gọi Ollama, Gemini và
OpenRouter qua cùng một contract, không đưa SDK hoặc chi tiết REST của provider
vào domain. Lớp này phải hỗ trợ structured/text generation, streaming,
embedding, retry/fallback/cancellation, role routing, physical-call planning,
config snapshot, connectivity check và redaction secret.

## 2. Những gì đã thực hiện

- Định nghĩa application contracts cho request, response, structured schema,
  capability, token usage, stream chunk, embedding, connectivity, provider
  target/route/config snapshot, logical role và execution mode.
- Định nghĩa inward-facing `ProviderPort` và router-level `ProviderGateway`.
- Triển khai `BaseProvider` dùng `httpx.AsyncClient` bất đồng bộ với lifecycle
  lazy, hỗ trợ injected client và phân biệt client do adapter sở hữu.
- Triển khai timeout/network/HTTP error mapping, retry transient error,
  `Retry-After`, exponential full-jitter backoff và cooperative cancellation.
- Triển khai parse structured JSON có bỏ code fence, sửa trailing comma có giới
  hạn, schema validation và một lần repair request.
- Port ba adapter REST:
  - Ollama: chat, NDJSON stream, embed và connectivity qua tags.
  - Gemini: `generateContent`, SSE stream, `embedContent` và model connectivity.
  - OpenRouter: chat completion, SSE stream, embeddings và models connectivity.
- Triển khai factory và router với role-specific provider/model, local-first
  routing, cloud opt-in, fallback chỉ cho lỗi được phép và fallback metadata.
- Triển khai `PhysicalCallPlanner`: Quality tách role; Fast fuse
  Planner+Simulator và Writer+Critic khi cùng target, đồng thời tự split nếu
  target/model khác nhau.
- Snapshot cấu hình chỉ chứa metadata an toàn, không chứa API key hoặc giá trị
  header; HTTP error message cũng che secret đã biết.
- Thêm mock contract suite dùng chung cho cả ba adapter và routing suite.

## 3. File/module quan trọng đã tạo hoặc thay đổi

- `src/application/contracts/providers.py`
  - Provider-neutral records, enums, errors, cancellation token và config
    snapshot.
- `src/application/ports/providers.py`
  - `ProviderPort` và `ProviderGateway`.
- `src/application/contracts/__init__.py`
  - Export các provider contract chính.
- `src/application/ports/__init__.py`
  - Export provider ports.
- `src/services/llm/base.py`
  - Async client lifecycle, HTTP mapping, retry/backoff/cancellation, structured
    repair và redaction.
- `src/services/llm/ollama.py`
- `src/services/llm/gemini.py`
- `src/services/llm/openrouter.py`
  - Ba adapter REST cụ thể.
- `src/services/llm/structured.py`
  - Parser/validator structured output.
- `src/services/llm/cancellation.py`
  - Compatibility export cho cancellation contract.
- `src/services/llm/factory.py`
  - Factory, role routing, fallback và physical-call planner.
- `src/services/llm/__init__.py`
  - Public service exports.
- `tests/services/test_provider_contracts.py`
  - Contract tests dùng cùng một suite cho Ollama, Gemini và OpenRouter.
- `tests/services/test_provider_routing.py`
  - Routing, fallback, cloud privacy gate và Quality/Fast split/fuse tests.

## 4. Quyết định triển khai đáng chú ý

- Provider details nằm dưới `src/services/llm`; application chỉ phụ thuộc
  contract/port, domain không import `httpx` hay provider adapter.
- Dùng REST async trực tiếp theo ADR-0005; không thêm OpenAI SDK hoặc một
  abstraction SDK trung gian.
- API key nhận từ `ProviderTarget.api_key`, environment variable hoặc header
  đã cấu hình; snapshot/log/error không trả secret.
- Cloud provider bị bỏ khỏi candidate list khi `allow_cloud=False`; route chỉ
  cloud sẽ fail rõ bằng `PrivacyRoutingError`, không âm thầm gửi dữ liệu ra
  ngoài.
- Fallback không áp dụng cho cancellation, authentication/configuration hoặc
  provider refusal; không dùng fallback để lách policy provider.
- Stream không retry sau khi đã phát token đầu tiên, vì không thể chắc request
  trước đó chưa hoàn tất.
- Fused call chỉ là execution plan: `logical_roles` vẫn được giữ riêng và
  target khác nhau sẽ buộc split. Schema/artifact cụ thể của từng role được để
  Phase 6 định nghĩa, đúng ranh giới Phase 5.
- Backoff dùng `Retry-After` khi provider trả về; nếu không có thì dùng
  exponential full-jitter. Các fixture đặt backoff bằng 0 để test nhanh và ổn
  định.

## 5. Tái sử dụng từ novel-ai-trans

- Tái sử dụng ý tưởng về base LLM service: lifecycle HTTP, metadata/error
  mapping, retry và cancellation safe points.
- Tái sử dụng ý tưởng endpoint mapping và response parsing cho Ollama, Gemini
  và OpenRouter.
- Tái sử dụng factory/fallback pattern và config snapshot pattern, nhưng đổi
  thành async provider-neutral contract, role routing và cloud privacy gate.
- Tái sử dụng ý tưởng cooperative cancellation; không copy toàn bộ repository
  hoặc logic translation.

## 6. Tests, lint và type-check

Các lệnh sau đều PASS:

- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run pytest tests/services/test_provider_contracts.py tests/services/test_provider_routing.py -q`
  - `26 passed`.
- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run pytest --ignore=tests/persistence -q`
  - `61 passed`.
- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run ruff check .`
  - PASS.
- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run ruff format --check .`
  - PASS, 82 files already formatted.
- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run pyright`
  - `0 errors, 0 warnings, 0 informations`.
- `git diff --check`
  - PASS.

Full pytest đã được chạy bằng `uv run pytest -vv --tb=short`. Suite thu thập 78
test, các test trước persistence đều PASS, sau đó tiến trình dừng tại
`tests/persistence/test_canonical_persistence.py::test_canonical_commit_writes_all_artifacts_and_is_idempotent`
không có traceback. Tiến trình đã được dừng sau hơn một phút để tránh treo
phiên làm việc. Đây là test persistence có sẵn, không import provider layer;
Phase 5 không sửa persistence. Vì vậy full-suite verification chưa thể ghi
PASS, nhưng test Phase 5 và toàn bộ test ngoài persistence đều PASS.

## 7. Tiêu chí hoàn tất

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Contract test giống nhau cho ba adapter | PASS | Cùng parametrized suite chạy trên Ollama, Gemini, OpenRouter; success, structured repair, embedding và connectivity đều xanh. |
| Mock tests bao phủ success, invalid JSON, timeout, rate limit, stream interruption và cancellation | PASS | `test_provider_contracts.py`, tổng 26 test Phase 5; mỗi adapter được chạy qua các nhánh chính. |
| Đổi provider/model theo từng role mà domain không đổi | PASS | `ProviderRequest`/`ProviderPort` trung lập; router test đổi planner/writer model và kiểm tra response contract không đổi. |
| Fuse/split calls vẫn giữ role artifacts độc lập | PASS ở execution/trace layer | `PhysicalCallPlan.logical_roles` giữ từng logical role đúng một lần; Fast fuse khi cùng target và split khi khác target. Schema validator/artifact models cụ thể thuộc Phase 6, chưa triển khai ở Phase 5. |

## 8. Vấn đề, technical debt và blocker còn lại

- Full pytest vẫn có một test persistence cũ bị treo như mô tả ở mục 6. Đây là
  blocker của full-suite verification, không phải lỗi được quan sát trong Phase
  5; cần điều tra riêng trước khi dùng full suite làm gate CI.
- Chưa có live-provider test; mọi test provider đều mock để không phát sinh
  network/API key ngoài ý muốn. Connectivity API đã có ở provider/router layer;
  public application/API use case sẽ nằm ở Phase 9–10.
- Role-specific Pydantic schemas, prompt registry/version/hash, semantic
  validators và artifact validation chưa làm trong Phase 5; đây là scope của
  Phase 6.
- Chưa có persistence record riêng cho LLM run trace; config snapshot contract
  đã sẵn sàng để application/graph lưu ở các phase sau.

## 9. Những việc của Phase tiếp theo nhưng CHƯA thực hiện

Phase 6 — Prompt và AI contracts chưa được thực hiện. Cụ thể chưa tạo:

- Các schema `TurnPlan`, `SimulationResult`, `SceneSpec`, `CritiqueResult` và
  các typed claim/state-operation proposal.
- Prompt registry/cache, prompt version/hash và prompt fixtures.
- Semantic validators, repair prompts và golden/snapshot tests.
- Ghi prompt/schema version vào LLM run.

## 10. Git diff/status và commit đề xuất

`git diff --check` đã PASS. Trạng thái hiện tại gồm hai file `__init__` đã sửa
và các file provider/test mới chưa commit; không có file nào được stage và
không chạy `git commit`, `git push` hay thay đổi lịch sử Git.

Commit message đề xuất:

```text
feat: implement Phase 5 provider layer
```
