# ADR-0012: ContentPolicy schema và enforcement đa tầng

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Giới hạn tuổi, rating, consent, chủ đề nhạy cảm và violence ceiling không thể
được bảo đảm bằng prompt text hoặc relationship score. Policy cần là dữ liệu
cấu trúc, deterministic và áp dụng trước khi Writer viết.

## Quyết định

`ContentPolicy` gồm `schema_version`, `rating`, topic boundaries,
`violence_ceiling`, `adult_explicit_opt_in`, consent requirements và player
overrides. Rating có thứ tự `teen_14_plus < mature_16_plus < adult_18_plus`;
effective policy là giao của world policy và player policy, trong đó player chỉ
có thể giữ nguyên hoặc thắt chặt.

Guard áp dụng age gate theo tuổi của mọi participant tại world time của scene:

- 14–15: chỉ teen-safe romance; không sexualization, explicit nudity,
  fetishization hay sexual behavior.
- 16–17: được mature emotional themes và intimacy không đồ họa; không explicit
  sexual description. Fade-to-black nếu cần chỉ là đề cập gián tiếp, không
  eroticize.
- 18+: explicit chỉ khi mọi participant từ 18, world/player cùng opt-in và
  consent hợp lệ.

Consent là state machine theo participant/activity/scene:
`not_discussed → requested → granted | declined`, và `granted → withdrawn`.
`declined`/`withdrawn` không tự thành granted; relationship score không phải
consent. Timeskip không hợp thức hóa scene trong quá khứ.

Scene tags và policy được kiểm tra tại World Builder, Planner/Simulator,
Claim Extractor, deterministic Guard, Writer input và Critic output. Khi bị
provider từ chối, không dùng fallback để lách policy; chỉ có thể hạ mức mô tả
theo lựa chọn hợp lệ.

## Invariant

- `adult_explicit` với participant dưới 18 luôn deny hoặc downgrade thành
  non-explicit safe alternative.
- Excluded topic và violence ceiling độc lập với rating.
- Writer chỉ nhận SceneSpec đã được Guard duyệt.
- Critic không được hợp thức hóa nội dung Guard đã cấm.
- Policy decision có mã lý do deterministic và fixture kiểm thử.

## Hệ quả

Safety policy có thể test không cần model thật, hiển thị warning trước confirm
world và kiểm toán theo participant/scene. Taxonomy mở rộng phải version schema
và thêm fixture, không đổi nghĩa tag cũ âm thầm.
