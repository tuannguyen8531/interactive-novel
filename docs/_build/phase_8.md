# Báo cáo Phase 8 — LangGraph turn pipeline

## 1. Mục tiêu của Phase

Xây dựng pipeline end-to-end cho một turn bằng fake provider deterministic, với
state graph bounded, typed AI artifacts, Domain Guard, checkpoint/resume,
cancellation, Quality/Fast policy và canonical commit boundary.

Phase 7 đã được commit trước khi bắt đầu Phase này:

```text
e8713b6 feat: add Phase 7 context and retrieval layer
```

## 2. Những gì đã thực hiện

- Thêm dependency LangGraph và SQLite checkpointer:
  - `langgraph>=1.2,<2.0` — lock hiện resolve `1.2.11`.
  - `langgraph-checkpoint-sqlite>=3.1,<4.0` — lock hiện resolve `3.1.1`.
- Define `TurnGraphState` bounded, chỉ chứa ID, input đã normalize, typed AI
  artifacts, retrieval manifests, patch payload, trace/event metadata, retry
  counters và commit status. Provider, `GameState`, ORM session và full history
  không đi vào checkpoint state.
- Implement nodes theo đúng thứ tự plan:
  - normalize input;
  - initial context;
  - planner/simulator;
  - claim extraction;
  - targeted evidence retrieval;
  - context validation;
  - Domain Guard;
  - bounded repair;
  - scene authorization và writer;
  - critic/revision;
  - canonical record construction;
  - atomic commit;
  - derived-job enqueue.
- Implement conditional edges và retry limits cho contract error, context
  insufficiency, Guard rejection và Writer/Critic revision.
- Implement `RoleExecutor`:
  - tái sử dụng `AIContractRegistry`, `PromptRegistry`, `ProviderPort` và
    `PhysicalCallPlanner` hiện có;
  - giữ output contract riêng cho từng logical role;
  - hỗ trợ optional `generate_fused_structured` cho fused physical call;
  - tự split về logical calls khi provider không có fused capability;
  - lưu `LLMRunTrace` và `physical_call_traces` secret-safe.
- Implement event sink bounded với vocabulary cho planner, simulator, context,
  validator, Guard, repair, writer, critic, commit, derived jobs, completion,
  failure và cancellation.
- Implement cooperative cancellation check ở boundary giữa node và trong role
  execution; cancellation trước commit không gọi committer.
- Implement checkpoint helpers:
  - `InMemorySaver` cho deterministic tests;
  - lazy `AsyncSqliteSaver` context manager cho production;
  - `checkpoint_config()` dùng `turn_run_id` làm LangGraph `thread_id`.
- Implement `CanonicalTurnBundle` builder từ patch đã Guard-approved. Claim
  proposals được chuyển thành typed domain claims trước khi Guard và commit;
  prose writer chỉ tạo `final_narrative`, không có quyền tạo canon.
- Cập nhật architecture test để phản ánh dependency direction trong plan:
  graph được dùng application contracts/ports, nhưng không được import API,
  CLI hoặc application use cases.
- Thêm fake-provider acceptance suite cho happy path, Fast/Quality, contract
  retry, Guard repair, cancellation, crash/resume và derived-job failure.

## 3. File/module quan trọng đã tạo hoặc thay đổi

- `pyproject.toml`, `uv.lock`
  - khai báo và lock LangGraph/SQLite checkpoint dependencies.
- `src/graph/state.py`
  - bounded `TurnGraphState` và `initial_graph_state()`.
- `src/graph/runtime.py`
  - runtime-only dependency bundle, request contract, committer và derived-job
    handler ports.
- `src/graph/builder.py`
  - StateGraph topology, conditional edges và retry routes.
- `src/graph/nodes.py`
  - toàn bộ Phase 8 node logic, cancellation/event boundary và AI → domain
    typed conversion.
- `src/graph/execution.py`
  - logical-role execution, contract parsing, fused/split physical calls và
    traces.
- `src/graph/records.py`
  - chuyển patch đã duyệt thành `CanonicalTurnBundle`.
- `src/graph/checkpoint.py`
  - InMemory/SQLite checkpoint factories và thread config.
- `src/graph/events.py`
  - `NodeEvent`, `EventSink`, in-memory sink và async publish boundary.
- `src/graph/pipeline.py`, `src/graph/__init__.py`
  - public runner, resume/cancel API và exports.
- `tests/graph/test_turn_pipeline.py`
  - 7 fake-provider tests.
- `tests/architecture/test_dependencies.py`
  - kiểm tra graph chỉ phụ thuộc application contracts/ports ở inward boundary.
- `docs/_build/phase_8.md`
  - báo cáo Phase này; thư mục `_build` đang được `.gitignore` bỏ qua theo
    convention hiện tại.

## 4. Quyết định triển khai đáng chú ý

- Runtime dependencies được capture bởi graph node closures, không nhét
  provider, ORM session hoặc `GameState` vào LangGraph state. Checkpoint là
  orchestration checkpoint, không phải game save.
- Canonical commit chỉ chạy sau khi context validation, typed patch và scene
  đã qua Guard. `DomainEngine` chỉ được dùng lại khi build record để tạo
  after-state; runtime `GameState` không bị mutate bởi graph.
- Claim proposals từ Simulator được materialize thành `AddKnowledgeClaim`
  domain operations trước Guard. Như vậy claim cũng chịu predicate, scope,
  time và reference validation như các state operation khác.
- Targeted manifest thiếu evidence tạo `ConsistencyStatus.INSUFFICIENT_EVIDENCE`
  deterministic; không cho Validator trả PASS ngầm khi không có evidence.
- Quality gọi Planner và Simulator tách physical call. Fast yêu cầu fused call
  nếu provider hỗ trợ; nếu không, executor tự split nhưng vẫn giữ từng logical
  artifact, contract và trace độc lập. Guard luôn chạy ở cả hai mode.
- Commit đánh dấu `commit_done` trước khi enqueue derived jobs. Derived-job
  handler lỗi chỉ ghi error và giữ `status=completed`, đúng invariant canonical
  turn không phụ thuộc derived artifacts.
- Retry được giới hạn: contract retry mặc định một lần, Guard/context repair
  mặc định một lần, Writer/Critic revision mặc định một lần.
- SQLite saver được import lazy và đóng qua async context manager. Test nhanh
  dùng `InMemorySaver` để không phụ thuộc database connection.

## 5. Những phần tái sử dụng từ novel-ai-trans

- Không copy toàn bộ repository và không đưa domain/model translation của
  novel-ai-trans vào codebase.
- Không có module novel-ai-trans nào được copy trực tiếp trong Phase này.
- Phase này tái sử dụng các abstraction đã được chuẩn hóa trong project từ
  strategy kế thừa của plan: `ProviderPort`, `ProviderRequest`,
  `PhysicalCallPlanner`, `AIContractRegistry`, `PromptRegistry`, retrieval
  `ContextAssembler`/`ClaimExtractor`, `DomainGuard` và
  `CanonicalTurnApplicationService` contract.

## 6. Tests, lint và type-check đã chạy

Mọi test/API command trong Phase đều có hard limit `30s`. Không có command nào
được để chạy quá thời hạn này.

- `timeout 30s uv run pytest tests/graph tests/architecture -q`
  - PASS — `10 passed`.
- `timeout 30s uv run pytest tests/api -q`
  - PASS — `2 passed`.
- `timeout 30s uv run pytest --ignore=tests/persistence -q`
  - PASS — `98 passed`.
- `timeout 30s uv run ruff check .`
  - PASS.
- `timeout 30s uv run ruff format --check .`
  - PASS — `117 files already formatted`.
- `timeout 30s uv run pyright`
  - PASS — `0 errors, 0 warnings, 0 informations`.
- `timeout 30s uv run python -c 'from langgraph.checkpoint.sqlite.aio import
  AsyncSqliteSaver; ...'`
  - PASS — import được `AsyncSqliteSaver`, thread config trả đúng
    `{"configurable": {"thread_id": "run-1"}}`.
- `git diff --check`
  - PASS.

### SQLite connection-level test

Không chạy connection-level SQLite checkpoint test trong sandbox. Các Phase
trước đã ghi nhận connection `aiosqlite` bị treo trong môi trường này; theo
quy tắc của Ân công, tiểu nữ không chờ quá 30 giây và không coi runtime SQLite
test là PASS. Import/config smoke test vẫn PASS; Ân công có thể tự chạy test
SQLite runtime ở môi trường phù hợp.

## 7. Tiêu chí hoàn tất

| Tiêu chí trong plan | Kết quả | Bằng chứng |
|---|---|---|
| Fake deterministic pipeline tạo một committed turn | PASS | `test_fake_pipeline_commits_one_canonical_turn`; committer nhận đúng một bundle có claim typed. |
| Crash giữa node có thể resume mà không double-commit | PASS | `test_checkpoint_resume_does_not_double_commit_after_one_crash`; resume qua cùng `thread_id`, committer chỉ nhận một bundle. |
| Guard rejection repair trong giới hạn | PASS | `test_guard_rejection_repairs_once_before_commit`; invalid location được sửa bằng lần Simulator tiếp theo, `repair=1`. |
| Cancellation trước commit không thay state | PASS | `test_cancellation_before_commit_leaves_canonical_boundary_untouched`; không gọi committer và GameState vẫn nguyên trạng. |
| Planner/Simulator fused và split cùng thỏa role-contract suite | PASS | Quality/Fast test cùng tạo narrative/patch; trace Fast có fused planner+simulator, Quality có split logical calls. Contract retry cũng được kiểm tra. |
| Derived job failure không đổi completed canonical turn | PASS | `test_derived_job_failure_preserves_completed_canonical_turn`; canonical bundle vẫn commit, status vẫn completed, derived error chỉ là retryable error. |

## 8. Vấn đề, technical debt hoặc blocker còn lại

- Runtime mở SQLite checkpoint chưa được xác minh trong sandbox do giới hạn
  `aiosqlite` nói trên. Đây là verification blocker của môi trường, không phải
  thay đổi kiến trúc; implementation và import/config smoke đã hoàn tất.
- `generate_fused_structured` hiện là optional extension ở provider runtime;
  ProviderPort cũ chưa bắt buộc capability fused. Provider không hỗ trợ fused sẽ
  tự động split và trace rõ `skip_reason`.
- Canonical record mapper là MVP: đã bao phủ các typed claim/state records cần
  cho fixture, nhưng các record phong phú hơn như thread/hook/tension cần được
  mở rộng khi application use cases và world builder đi vào Phase 9/12.
- Graph hiện chưa expose REST/SSE/background job lifecycle; đó là scope của
  Phase 9–10, chưa thực hiện trong Phase này.

## 9. Những việc dự kiến của Phase tiếp theo nhưng CHƯA thực hiện

Phase 9 chưa được bắt đầu. Các việc còn để lại gồm application use cases cho
world, playthrough, submit/get/cancel turn, branch, character/memory/
relationship queries, provider settings, export, idempotency và concurrency
policy.

## 10. Git diff, git status và commit message đề xuất

Đã kiểm tra `git diff --check` và `git status --short`.

Working tree hiện có:

- modified: `pyproject.toml`, `uv.lock`;
- modified: `tests/architecture/test_dependencies.py`;
- modified: `src/graph/__init__.py`;
- untracked: các module Phase 8 trong `src/graph/`;
- untracked: `tests/graph/test_turn_pipeline.py`;
- `docs/_build/phase_8.md` được tạo nhưng nằm trong thư mục ignored.

Tiểu nữ không chạy `git commit`, không push và không thay đổi lịch sử Git cho
Phase 8.

Commit message đề xuất:

```text
feat: add Phase 8 LangGraph turn pipeline
```
