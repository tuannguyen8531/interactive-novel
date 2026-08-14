# ADR-0013: Semantics của branch, fork và regenerate

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Người chơi cần thử lại và rẽ nhánh nhưng không được làm lẫn event, memory,
relationship hoặc secret giữa các timeline.

## Quyết định

Branch root có `parent_branch_id = null`, `fork_turn_id = null` và revision
riêng. Branch con lưu parent, fork turn và depth; tại fork nó kế thừa ancestor
đến đúng fork turn (inclusive), rồi có head/revision độc lập.

Mọi canonical record có branch scope. Query branch luôn resolve ancestry theo
fork boundary trước khi lọc time/owner. Sibling và future của parent sau fork
không hiển thị cho child. Head update dùng optimistic concurrency trên
`base_revision`; stale turn không commit.

Regenerate mặc định tạo branch mới từ parent turn, không ghi đè lịch sử đã công
bố. Undo chỉ di chuyển head về ancestor khi branch chưa có descendant sau điểm
đó; nếu đã có descendant, dùng fork mới để giữ lịch sử. MVP không merge branch.

Branch lifecycle: `active → abandoned`; abandon không xóa records và không
được tái sử dụng như branch active nếu chưa có use case explicit.

## Invariant

- Root history luôn giữ được.
- Không sibling/future leakage.
- Fork không copy thành hai canonical event mới; ancestry là quan hệ query.
- Regenerate không phá turn cũ.
- Failed/stale commit không đổi branch head.

## Hệ quả

Replay và export có thể xác định timeline bằng ancestry + local events. Index,
summary và embedding phải mang branch/source revision để stale đúng cách.
