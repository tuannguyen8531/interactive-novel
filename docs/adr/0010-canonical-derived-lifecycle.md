# ADR-0010: Canonical và derived data

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Turn cần ghi nhiều record cùng nhau, trong khi summary, embedding và index có
thể lỗi hoặc tái tạo. Nếu trộn chúng vào transaction, lỗi phụ làm mất dữ liệu
đúng; nếu để prose quyết định canon, engine mất authority.

## Quyết định

Canonical transaction ghi nguyên tử:

- turn và final narrative;
- events/participants;
- typed claims, CanonFacts và claim links;
- observations, beliefs và evidence;
- current character/state changes;
- relationship/tension changes;
- thread/hook changes;
- branch head/revision;
- outbox/derived-job intent tối thiểu.

Sau commit mới phát SSE `completed` và enqueue derived jobs. Summary,
embedding, retrieval/FTS index, consolidation, analytics và snapshot là derived:
có version, source revision, builder provenance, content hash, idempotency key
và retry policy. Derived failure không rollback canonical turn; read path
fallback về current state và raw/recent events.

Raw prompt/output không lưu mặc định; chỉ lưu metadata trace cần thiết theo
privacy/debug policy.

## Invariant

- Canonical commit all-or-nothing.
- `completed` chỉ phát sau commit thành công.
- Derived artifact không được quyết định canon.
- Reconciler có thể dựng lại artifact thiếu sau outbox dispatch interruption.
- Retry derived job không double-effect canonical data.

## Hệ quả

Correctness và privacy không phụ thuộc provider, summarizer hay embedding. Hệ
thống chấp nhận context tạm thời kém giàu hơn khi derived artifact chưa sẵn sàng.
