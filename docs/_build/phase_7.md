# Báo cáo Phase 7 — Context và retrieval

## 1. Mục tiêu của Phase

Xây dựng lớp context/retrieval có thể cung cấp đúng dữ liệu, đúng góc nhìn và
không vượt token budget cho từng AI role. Hard scope phải được áp dụng trước
scoring hoặc embedding để không làm lộ dữ liệu từ owner, branch hoặc thời điểm
không hợp lệ.

## 2. Những gì đã thực hiện

- Tạo retrieval contracts cho:
  - `RetrievalScope`, bao gồm playthrough, branch ancestry, world time, owner
    và public visibility.
  - `MemoryCandidate` cho event, claim, observation, belief, thread, hook và
    state.
  - `RetrievalQuery`, `RetrievalHit`, `ScoreBreakdown` và
    `RetrievalTrace`.
  - `InitialContextRequest`, `InitialContextManifest` và `ContextEntry`.
  - `EmbeddingMetadata`, `EmbeddingRecord` và content hash ổn định.
  - `ClaimExtractionResult`.
- Implement `HardScopeFilter` với các hard filter theo playthrough, branch
  ancestry, branch scope, world time, validity range, owner và visibility.
- Implement deterministic retrieval scoring theo recency, salience, emotional
  intensity, entity, goal, thread, lexical và exact claim/fingerprint match.
- Implement recent-event marking, source deduplication và token budget allocator
  theo role.
- Implement `ContextAssembler` cho initial context:
  - lọc và deduplicate trước ranking;
  - xếp hạng rồi chọn theo `max_items` và token budget;
  - tạo manifest có ID, scope, trace ID và embedding metadata.
- Implement optional embedding path:
  - dùng `ProviderPort.embed`, tương thích với Ollama nhưng không khóa domain
    vào adapter cụ thể;
  - embedding tắt hoặc provider lỗi vẫn fallback về retrieval deterministic;
  - dùng NumPy exact cosine khi có NumPy, có pure-Python fallback khi không có;
  - lưu model, dimensions, embedding version và SHA-256 content hash.
- Implement `ClaimExtractor`:
  - chỉ đọc typed claim/state proposals;
  - tạo `KnowledgeRequirement` và `ValidationQuery` deterministic;
  - giữ mapping claim → mutation được tham chiếu, không parse prose.
- Implement `TargetedConsistencyRetriever`:
  - lọc hard scope trước;
  - exact claim ID/fingerprint lookup được ưu tiên tuyệt đối;
  - semantic/lexical và optional embedding fallback chỉ dùng khi không có exact
    candidate hợp lệ;
  - trả `TargetedEvidenceManifest` với `insufficient_evidence=True` khi không
    có evidence có thể chứng minh.
- Implement in-memory trace store và SQLite adapters cho candidate sources,
  embedding metadata/vector và retrieval trace. Vector được lưu dạng BLOB theo
  thiết kế SQLite MVP; trace chỉ lưu ID, score, scope và metadata an toàn, không
  lưu raw prompt/output.
- Bổ sung retrieval repository vào Unit of Work và candidate converters cho
  narrative thread/hook cùng event, claim, observation và belief.
- Thêm Alembic migration `0003_context_retrieval` và kiểm tra schema kỳ vọng.

## 3. File/module quan trọng đã tạo hoặc thay đổi

- `src/application/contracts/retrieval.py`
  - retrieval scope/query/manifest, candidate, score, embedding và trace
    contracts.
- `src/application/ports/retrieval.py`
  - ports cho candidate source, embedding store và trace store.
- `src/services/retrieval/`
  - `scope.py`: hard visibility/time/branch filter.
  - `scoring.py`: deterministic hybrid scoring.
  - `budget.py`: role-aware token budget.
  - `context.py`: initial context và targeted retrieval orchestration.
  - `claims.py`: Claim Extractor.
  - `embeddings.py`: optional embedding/index/cosine path.
  - `sources.py`: canonical-record → retrieval-candidate adapters.
  - `tracing.py`: in-memory trace sink.
- `src/services/persistence/retrieval.py`
  - SQLite candidate repository, durable embedding store và trace store.
- `src/services/persistence/models.py`
  - `MemoryEmbeddingModel` và `RetrievalTraceModel`.
- `alembic/versions/0003_context_retrieval.py`
  - bảng `memory_embeddings` và `retrieval_traces`.
- `src/application/ports/persistence.py`,
  `src/services/persistence/uow.py`
  - expose retrieval source qua Unit of Work.
- `tests/services/test_context_retrieval.py`
  - kiểm tra hard scope, coffee-memory recall, exact claim/fingerprint,
    insufficient evidence, Claim Extractor, cosine và embedding metadata.
- `tests/persistence/test_migrations.py`
  - bổ sung hai bảng derived mới vào expected schema.

## 4. Quyết định triển khai đáng chú ý

- Scope là boundary bảo mật bắt buộc: candidate không được đi vào scorer,
  embedding hoặc prompt nếu chưa qua hard filter.
- Branch con chỉ nhận branch hiện tại và ancestry; sibling/future bị loại trước
  ranking. Claim/observation/belief hết validity cũng bị loại khỏi evidence
  hiện tại.
- Public memory không cần owner; private/owner memory chỉ được đưa vào context
  khi `scope.owner_id` khớp.
- Exact claim/fingerprint là nguồn ưu tiên cho targeted validation, tránh để
  semantic similarity thay thế bằng chứng typed.
- Embedding là derived data, có thể rebuild và không có quyền quyết định canon.
  Model/version/hash/dimensions được lưu cùng vector để tránh dùng stale vector.
- Trace không chứa raw query text hoặc model output. Trace có score breakdown,
  selected/dropped reason và embedding score để audit retrieval.
- Token estimation dùng quy tắc ổn định khoảng bốn ký tự mỗi token; đây là
  allocator MVP, chưa phụ thuộc tokenizer của một model cụ thể.
- Không thêm NumPy vào dependency bắt buộc; deployments tối giản vẫn chạy bằng
  cosine pure Python.

## 5. Tái sử dụng từ novel-ai-trans

- Không copy toàn bộ repository và không port domain translation.
- Tái sử dụng đúng boundary/provider pattern đã có trong dự án: `ProviderPort`
  cung cấp async `embed`, để retrieval không phụ thuộc trực tiếp vào Ollama
  client.
- Tái sử dụng ý tưởng adapter/port, async lifecycle và test fake provider từ
  inventory Phase 0/Phase 5; các contract retrieval, scope và evidence đều được
  viết mới cho interactive novel.

## 6. Tests, lint và type-check

- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache timeout 30s uv run pytest tests/services/test_context_retrieval.py -q`
  - PASS — `8 passed`.
- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache timeout 30s uv run pytest --ignore=tests/persistence -q`
  - PASS — `91 passed`.
- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache uv run ruff check .`
  - PASS.
- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache uv run ruff format --check .`
  - PASS — `107 files already formatted`.
- `UV_CACHE_DIR=/tmp/interactive-novel-uv-cache uv run pyright`
  - PASS — `0 errors, 0 warnings, 0 informations`.
- `timeout 30s env UV_CACHE_DIR=/tmp/interactive-novel-uv-cache uv run alembic upgrade head --sql`
  - PASS — migration offline sinh đúng `memory_embeddings` với `vector BLOB`
    và `retrieval_traces`.
- `git diff --check`
  - PASS.

`tests/persistence/test_migrations.py` đã được chạy với giới hạn đúng 30 giây
nhưng không trả output và bị dừng bởi timeout. Đây là giới hạn sandbox khi
`aiosqlite` mở connection, đã từng xuất hiện ở các Phase persistence trước; tiểu
nữ không coi runtime migration test này là PASS và không tiếp tục chờ quá hạn.

## 7. Tiêu chí hoàn tất

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| NPC không retrieve secret chưa biết | PASS | `test_initial_context_hard_filters_owner_branch_and_future` loại private memory của owner khác trước context. |
| Branch con không thấy future/sibling events | PASS | Cùng test loại sibling branch và event ở world time tương lai. |
| Retrieval chạy khi embeddings tắt | PASS | Coffee scenario chạy không provider/embedding và manifest không có embedding model. |
| Coffee-memory scenario lấy đúng memory sau noise | PASS | `test_coffee_memory_survives_noise_without_embeddings`; claim ưu tiên hơn 18 event nhiễu. |
| Targeted retrieval tìm claim/evidence ngoài initial context | PASS | Exact claim test gọi targeted phase độc lập và trả đúng `EvidenceReference`. |
| Thiếu evidence trả `insufficient_evidence`, không PASS ngầm | PASS ở Phase 7 contract boundary | `TargetedEvidenceManifest` bắt buộc trạng thái explicit và test scope-filtered evidence trả `insufficient_evidence=True`; validator node end-to-end thuộc Phase 8. |

## 8. Vấn đề, technical debt và blocker còn lại

- Runtime SQLite persistence test không hoàn tất trong sandbox do connection
  `aiosqlite` bị treo; offline Alembic generation và toàn bộ test ngoài
  persistence vẫn PASS. SQLite adapters chưa có runtime verification trong môi
  trường hiện tại.
- Embedding provider thật chưa được gọi; test dùng fake provider. Ollama/model
  cụ thể vẫn là lựa chọn runtime, không chốt trong Phase 7.
- SQL repository hard-prefilter world time trực tiếp cho event/claim/
  observation/belief. Thread/hook hiện lấy world time từ payload vì schema
  canonical hiện có chưa có cột world time riêng; `ContextAssembler` vẫn áp
  hard filter cuối cùng trước ranking.
- Weight scoring và token estimate mới là cấu hình MVP, cần scenario evaluation
  để tune sau khi pipeline chạy end-to-end.
- Validator chưa được nối thành graph node; Phase 7 chỉ cung cấp targeted
  evidence manifest và trạng thái thiếu evidence cho Phase 8.

## 9. Những việc của Phase 8 nhưng CHƯA thực hiện

- Chưa tạo `TurnGraphState` và LangGraph turn pipeline.
- Chưa nối các node normalize input, initial context, plan, simulate, extract
  claims, targeted retrieval, validate, Guard, repair, writer, critic,
  canonical commit và derived-job enqueue.
- Chưa thêm conditional edges, retry limits, SQLite checkpoint, cancellation
  checks, quality/fast policy hoặc fake-provider end-to-end test.

## 10. Git diff/status và commit đề xuất

- `git diff --check`: PASS.
- Working tree hiện có các thay đổi Phase 7 chưa commit trong contracts, ports,
  retrieval services, persistence adapters/models, migration và tests. Không
  chạy `git commit`, không push và không thay đổi lịch sử Git.
- `docs/_build/phase_7.md` đã được tạo theo yêu cầu; thư mục `docs/_build/`
  đang bị `.gitignore` bỏ qua như các report trước.

Commit message đề xuất:

```text
feat: add Phase 7 context and retrieval layer
```
