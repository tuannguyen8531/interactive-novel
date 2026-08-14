# ADR-0003: Event log, current state và snapshot

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Save/load, undo, regenerate, fork và audit cần lịch sử bất biến; đọc scene lại
cần current state nhanh. Một bản snapshot duy nhất không đủ để audit và một
event log thuần sẽ làm read path không cần thiết chậm.

## Quyết định

Dùng mô hình hybrid:

```text
canonical event/change log + canonical current-state tables
                         ↓
                derived snapshot/checksum
```

Event là sự thật bất biến sau commit. Current-state tables là projection có
thẩm quyền được cập nhật trong cùng canonical transaction. Snapshot là
acceleration artifact chứa revision, branch, clock, RNG state, active claims,
beliefs, relationships, threads, schema version và checksum; snapshot có thể
xóa và tái tạo từ canonical data.

Narrative text chỉ là output của turn, không phải nguồn canon. Correction tạo
event/claim hiệu chỉnh có provenance, không sửa im lặng event cũ.

## Invariant

- Replay events từ ancestor/snapshot phải tái tạo cùng canonical state.
- Snapshot stale hoặc hỏng không được ngăn canonical read; fallback về current
  tables và raw/recent events.
- Snapshot không được xóa event history.
- Mọi canonical change có turn, branch, world time và provenance.

## Hệ quả

Read path nhanh, replay và audit rõ, còn snapshot job có thể retry độc lập.
Schema/version/content hash phải được lưu để phát hiện artifact stale.

## Không làm trong MVP

Không thay event history bằng summary, embedding, vector index hoặc narrative
summary.
