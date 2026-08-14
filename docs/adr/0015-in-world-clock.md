# ADR-0015: Đồng hồ trong truyện

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Event, observation, scheduled trigger và branch replay cần thứ tự thời gian
deterministic. Cho mọi turn tăng một lượng cố định sẽ không phù hợp với lời
thoại, di chuyển và timeskip.

## Quyết định

Mỗi Playthrough có một `InWorldClock`. Canonical clock là số phút nguyên kể từ
`world_epoch`; timezone chỉ phục vụ hiển thị. Mỗi committed turn có
`world_time_start`, `duration_minutes` và `world_time_end`; duration do Planner
đề xuất, nhưng Guard clamp theo action class. Mặc định action có duration 1
phút; meta/action không làm thời gian trôi có thể dùng 0. Không turn nào làm
clock lùi trên cùng branch.

Branch kế thừa clock tại fork rồi tiến độc lập. UTC timestamp vẫn được lưu cho
audit, nhưng không thay thế in-world time. ScheduledEvent dùng world time và
chỉ materialize theo ADR-0011. RNG seed/state thuộc playthrough/branch và chỉ
dùng tại rule/check đã khai báo; không dùng random ngầm để che mutation.

Tuổi nhân vật tại scene được tính từ birth date/age anchor và world time. Một
timeskip chỉ ảnh hưởng scene sau nó; không retroactively sửa age hoặc policy của
scene cũ.

## Invariant

- `world_time_end >= world_time_start` và branch-local time không lùi.
- Event ordering không phụ thuộc wall-clock của máy.
- Replay dùng cùng duration và RNG state để cho cùng kết quả.
- Một action không được tự ý chọn duration ngoài policy class.
- Off-screen không tự chạy chỉ vì clock tiến.

## Hệ quả

Planner có thể đề xuất pacing và scheduled trigger có semantics rõ. UI hiển
thị world time theo timezone của world/playthrough, còn persistence giữ integer
minutes và UTC audit timestamp.
