# State machines

Các state dưới đây là state sản phẩm/canonical. Node phase và SSE event có thể
chi tiết hơn nhưng không được tạo một lifecycle khác với các transition này.

## 1. Turn

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running: runner nhận job
    queued --> cancelled: cancel trước khi chạy
    running --> running: repair/retry trong giới hạn
    running --> failed: provider/validation/persistence lỗi trước commit
    running --> cancelled: cancel trước commit
    running --> completed: canonical commit thành công
    completed --> [*]
    failed --> [*]
    cancelled --> [*]
```

`committing` là internal phase/SSE event nằm trong `running`; transaction
thành công mới đổi status thành `completed`. Nếu cancellation đến sau commit,
turn vẫn `completed` và UI không được hiển thị `cancelled` giả.

Canonical guards:

- `queued → running` chỉ một runner sở hữu `turn_run_id`;
- `running → completed` chỉ qua một canonical commit idempotency key;
- lỗi/cancel trước commit không để state patch dở;
- base revision stale làm turn `failed` với mã giải thích, không đổi head.

## 2. Background job

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running: runner start
    queued --> cancelled: cancel/force-stop trước start
    running --> cancelling: cancel requested
    cancelling --> cancelled: safe point hoặc force stop hoàn tất
    running --> completed: turn/save commit xong
    running --> failed: lỗi không phục hồi
    cancelling --> completed: commit đã hoàn tất trước cancel
    completed --> [*]
    failed --> [*]
    cancelled --> [*]
```

Job status phục vụ điều phối/SSE; `Turn.status` vẫn là authority của turn.
Restart app đánh dấu job non-terminal đang chạy thành `failed/interrupted`,
không tự đoán rằng canonical commit đã xảy ra. Reconnect đọc snapshot REST rồi
mới nhận event còn trong buffer.

## 3. Branch

```mermaid
stateDiagram-v2
    [*] --> active: create root hoặc fork
    active --> active: commit turn / switch view
    active --> abandoned: user abandon
    abandoned --> [*]
```

Branch con không phải bản copy event. Nó giữ `parent_branch_id`,
`fork_turn_id`, `depth`, `head_turn_id`, `head_revision` và query ancestry. Root
không có parent/fork. Regenerate tạo branch mới; undo chỉ move head khi không
có descendant sau điểm undo.

## 4. Consent

Consent là state machine theo `(scene_id, participant_id, activity_tag)`:

```mermaid
stateDiagram-v2
    [*] --> not_discussed
    not_discussed --> requested: explicit request
    requested --> granted: clear affirmative consent
    requested --> declined: refusal or no consent
    granted --> withdrawn: explicit withdrawal
    declined --> requested: new explicit request
    withdrawn --> requested: new explicit request
```

Không có transition tự động từ relationship score, blush, silence, intoxication
hoặc prior consent. `declined`/`withdrawn` chặn activity hiện tại cho tới khi
có request mới và affirmative consent phù hợp; age/rating/policy vẫn phải pass.

## 5. Content decision

Guard trả một trong ba kết quả deterministic:

| Decision | Nghĩa |
|---|---|
| `allow` | SceneSpec đúng age/rating/topic/violence/consent |
| `downgrade` | Outcome/story beat có thể giữ nhưng phải hạ tag/mức mô tả |
| `deny` | Không được materialize scene hoặc proposal |

Decision có `reason_codes`, participant ages, effective policy version và
`evaluated_world_time`; không dùng text model để thay quyết định Guard.
