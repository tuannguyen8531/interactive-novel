# Báo cáo Phase 6 — Prompt và AI contracts

## 1. Mục tiêu của Phase

Định nghĩa input/output versioned cho các AI role, để output của fake provider
có thể parse và validate độc lập trước khi đi vào graph/Guard. Prompt phải là
asset có version, schema version, hash và cache; authoritative proposal phải
được biểu diễn bằng typed claim hoặc typed state operation.

## 2. Những gì đã thực hiện

- Tạo Pydantic contracts strict (`extra="forbid"`) cho 11 schema được plan yêu
  cầu:
  - `TurnPlan`.
  - `SimulationResult`.
  - `KnowledgeClaimProposal`.
  - `KnowledgeRequirement`.
  - `ValidationQuery`.
  - `TargetedEvidenceManifest`.
  - `ConsistencyReport`.
  - `StatePatchProposal`.
  - `SceneSpec`.
  - `CritiqueResult`.
  - `WorldSeed`.
- Bổ sung các contract hỗ trợ cần cho mục tiêu “mọi role có input/output
  versioned”: `RoleInput`, `NarrativeDraft`, `AIProvenance`, `LLMRunTrace` và
  `TokenUsageSnapshot`.
- Biểu diễn state mutation bằng discriminated union `StateOperation`: advance
  clock, location/condition/psychology, relationship delta, claim/link/canon
  fact, observation/belief, thread và consent transition. Free-form mutation
  không parse được.
- Kiểm tra predicate registry, object/value exclusivity, branch/time scope,
  relationship self-edge, world seed reference/identity và draft SceneSpec
  không được tự nhận Guard approval.
- Tạo `AIContractRegistry` để map role → Pydantic model, parse JSON/payload,
  tạo `StructuredSchema` cho Phase 5 provider và trả diagnostic theo field.
- Tạo prompt manifest và sáu prompt role: World Builder, Planner, Simulator,
  Context Validator, Writer, Critic.
- Tạo `PromptRegistry` với file-backed template loading, semantic/schema
  metadata, SHA-256 template hash, required variable check, role-matching
  `RoleInput` rendering và context-local prompt cache.
- Tạo repair prompt có role, schema và diagnostic; không đưa raw output vào
  `LLMRunTrace`.
- Tạo builder ghi provider/model/request/timing/token/retry/fallback cùng
  `prompt_version`, `output_schema_version` và `config_snapshot_id` vào
  `LLMRunTrace`.
- Thêm fake AI fixtures, supporting retrieval fixtures và prompt golden
  snapshots.

## 3. File/module quan trọng đã tạo hoặc thay đổi

- `src/application/contracts/ai.py`
  - Enums, versioned role outputs, typed claims, requirements, evidence,
    discriminated state operations, WorldSeed, SceneSpec và LLM trace.
- `src/application/contracts/__init__.py`
  - Export các AI contracts chính.
- `src/services/ai/contracts.py`
  - Role-to-model registry, parse JSON/Pydantic và diagnostics.
- `src/services/ai/validators.py`
  - Semantic/reference/authority validation sau Pydantic shape validation.
- `src/services/ai/tracing.py`
  - Build secret-safe `LLMRunTrace` từ provider response và prompt definition.
- `src/services/ai/__init__.py`
  - Public AI contract service exports.
- `src/services/prompts/registry.py`
  - Prompt manifest loader, cache, renderer, snapshot và repair prompt.
- `src/services/prompts/__init__.py`
  - Public prompt service exports.
- `src/prompts/manifest.json`
- `src/prompts/{world_builder,planner,simulator,context_validator,writer,critic}.md`
- `src/prompts/repair.md`
  - Prompt assets, metadata và repair template.
- `tests/fixtures/ai/role_outputs.json`
- `tests/fixtures/ai/supporting_contracts.json`
- `tests/fixtures/prompts/phase_6_snapshots.json`
  - Fake output/supporting fixtures và golden template hashes.
- `tests/services/test_ai_contracts.py`
- `tests/services/test_prompt_registry.py`
  - Parse, diagnostic, typed mutation, semantic, trace, cache và golden tests.

## 4. Quyết định triển khai đáng chú ý

- Pydantic nằm ở application contract boundary; domain vẫn không import
  Pydantic, prompt service hay provider implementation.
- Tất cả AI output yêu cầu `schema_version`, `role`, `run_id` và
  `prompt_version`; registry kiểm tra role/schema khớp contract trước khi trả
  output.
- `StateOperation` dùng discriminator `operation_type`, nên payload tùy ý hoặc
  operation chưa đăng ký bị từ chối ngay lúc parse.
- `KnowledgeClaimProposal` chỉ cho predicate trong registry đã khóa và bắt buộc
  đúng một trong `object_id`/`typed_value`. Direct familiarity mutation không có
  trong relationship operation enum.
- `TargetedEvidenceManifest` rỗng phải ghi rõ `insufficient_evidence`; validator
  không cho phép biến thiếu evidence thành PASS ngầm.
- `WorldSeed` luôn là draft, `opening_scene.guard_approved` phải false; việc
  user confirm/persistence thuộc phase sau.
- Prompt text không nằm trong graph/node code. Registry phát hiện placeholder
  không khai báo, thiếu biến và unresolved variable; golden test phát hiện
  template thay đổi ngoài ý muốn.
- `LLMRunTrace` chỉ lưu metadata và mặc định `raw_output_stored=false`, phù hợp
  với quy định không lưu raw prompt/output mặc định.
- `NarrativeDraft` là output contract tối thiểu cho Writer để đáp ứng yêu cầu
  mọi role có output versioned; nó chỉ chứa prose/beat mapping, không chứa
  state patch.

## 5. Tái sử dụng từ novel-ai-trans

- Tái sử dụng ý tưởng file-backed prompt loader từ
  `src/prompts/__init__.py`: template asset riêng, placeholder rendering và
  path resolution.
- Tái sử dụng ý tưởng context-local cache từ `src/services/generation/cache.py`
  và prompt cache scope; chuyển thành cache immutable theo job/context.
- Tái sử dụng ý tưởng template hash/version từ prompt generation flow; mở rộng
  thành manifest có role, input contract, output schema version và changelog.
- Không copy prompt translation, crawler selectors, translation state hay toàn
  bộ repository tham chiếu.

## 6. Tests, lint và type-check

Các lệnh sau PASS:

- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run pytest tests/services/test_ai_contracts.py tests/services/test_prompt_registry.py -q`
  - `22 passed`.
- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run pytest --ignore=tests/persistence -q`
  - `83 passed`.
- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run ruff check .`
  - PASS.
- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run ruff format --check .`
  - PASS, 92 files already formatted.
- `UV_CACHE_DIR=/tmp/interactive_novel_uv_cache uv run pyright`
  - `0 errors, 0 warnings, 0 informations`.
- `git diff --check`
  - PASS.

Full suite có 20-second timeout và dừng sau 35 test tại nhóm persistence; test
cụ thể
`tests/persistence/test_canonical_persistence.py::test_canonical_commit_writes_all_artifacts_and_is_idempotent`
cũng không hoàn tất trong 10 giây. Đây là vấn đề đã tồn tại từ Phase 5, không
được Phase 6 chạm tới; test Phase 6 và toàn bộ suite ngoài persistence đều
PASS.

## 7. Tiêu chí hoàn tất

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| Fake provider fixtures parse đúng | PASS | 22 test contract/prompt; fixtures cho sáu role output và supporting validation/evidence contracts parse thành Pydantic model. |
| Mọi authoritative proposal dùng typed claim/state operation | PASS | `KnowledgeClaimProposal`, `StatePatchProposal` và discriminated `StateOperation`; test free-form operation/predicate không hợp lệ bị từ chối. |
| Schema lỗi tạo diagnostic rõ | PASS | `AIContractValidationError` trả path/code/message; test kiểm tra field path, semantic error và invalid JSON không lộ raw text. |
| Prompt snapshot/golden tests phát hiện thay đổi ngoài ý muốn | PASS | Manifest snapshot so hash SHA-256 của sáu prompt role cùng semantic/input/output versions; repair/render/cache đều có test. |

## 8. Vấn đề, technical debt và blocker còn lại

- Full pytest vẫn bị treo ở persistence test cũ như mục 6; đây là blocker của
  full-suite verification/CI gate, không phải lỗi Phase 6 quan sát được.
- `LLMRunTrace` và semantic contracts mới là application contract/builder; chưa
  có bảng persistence hoặc use case lưu LLM run. Phần đó thuộc application/
  pipeline phases sau.
- Semantic validators hiện kiểm tra shape/reference/authority boundary nhưng
  chưa chuyển proposal thành domain dataclass hoặc chạy Guard đầy đủ; Guard và
  canonical commit nằm ở Phase 8.
- Prompt registry đang đọc asset từ source tree; cần xác nhận package-data khi
  đóng wheel/deploy production.
- Chưa gọi provider thật; Phase 6 chỉ dùng fake fixtures và golden assets để
  giữ test deterministic.

## 9. Những việc của Phase tiếp theo nhưng CHƯA thực hiện

Phase 7 — Context và retrieval chưa được thực hiện. Chưa có:

- Initial Context Manifest và token budget allocator.
- Branch/time/owner hard filters.
- Recent event/entity/goal/thread retrieval và scoring.
- Ollama embeddings, embedding metadata/hash/version và NumPy re-rank.
- Claim Extractor, Targeted Consistency Retriever và exact fingerprint lookup.
- Retrieval trace hoặc scenario kiểm thử memory/evidence leak.

## 10. Git diff/status và commit đề xuất

Sau Phase 5 commit `994b5f6`, Phase 6 hiện là thay đổi chưa commit. `git
diff --check` đã PASS; không có file nào được stage, không commit/push và không
thay đổi lịch sử Git trong Phase 6.

Commit message đề xuất:

```text
feat: add Phase 6 AI contracts and prompt registry
```
