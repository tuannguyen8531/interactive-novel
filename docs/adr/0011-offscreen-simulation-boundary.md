# ADR-0011: Ranh giới mô phỏng ngoài camera

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Tick toàn bộ NPC sau mỗi turn làm scope tăng đột biến, khó replay và tạo thay
đổi không người chơi quan sát được. MVP chỉ cần materialize thay đổi ngoài màn
hình khi chúng có nguyên nhân và liên quan.

## Quyết định

MVP chỉ materialize off-screen change khi có ít nhất một trigger:

1. `ScheduledEvent` đã khai báo.
2. `NarrativeThread` có mốc tiến triển đến hạn.
3. Planner đề xuất một diễn biến cần cho scene hiện tại và Guard xác nhận
   causal chain.

Mỗi off-screen event có actor, world time, location, cause references,
visibility và typed claim/state operation như event on-screen. Không tạo
retroactive event mâu thuẫn với canon/observation đã có.

## Invariant

- Không autonomous tick toàn bộ NPC sau mỗi turn.
- Không tự phát rumor propagation ngoài trigger.
- Không materialize thay đổi chỉ vì một khoảng thời gian trôi qua nếu không có
  scheduled/thread cause.
- Off-screen không phải đường vòng để Writer tạo canon.

## Hệ quả

WorldScheduler, NPCAgenda, WorldTick và simulation toàn thế giới có thể bổ sung
sau bằng ADR mới mà không đổi event/claim contract hiện tại.
