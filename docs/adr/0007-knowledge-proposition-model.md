# ADR-0007: Typed knowledge proposition, fact identity và predicate registry

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

LLM có thể viết một câu nghe như sự thật nhưng không thể trao quyền canon cho
prose. Engine cần kiểm tra mâu thuẫn, scope, thời gian, evidence và quyền biết.

## Quyết định

Mọi fact hoặc state mutation có thẩm quyền phải đi qua typed domain claim hoặc
typed state operation. `KnowledgeClaim` tối thiểu có:

```text
claim_id, claim_type, subject_id,
predicate, object_id | typed_value, polarity,
qualifiers, valid_time, branch_scope,
schema_version, normalized_fingerprint, provenance
```

`CanonFact` là assertion có thẩm quyền lên claim, với status `active`,
`retracted` hoặc `superseded`, source event/rule, asserted turn/time và
`superseded_by`. `ClaimLink` chỉ nhận loại đã đăng ký:
`supports`, `contradicts`, `derived_from`, `refines`, `supersedes`.

MVP dùng predicate registry hữu hạn, versioned. Registry ban đầu gồm
`located_at`, `age_is`, `romantic_interest`, `commitment_status`, `goal_active`,
`secret_exists`, `item_held`, `physical_condition`, `public_fact` và
`event_participation`. Relationship delta, time advance, thread transition và
character-state delta là typed operations riêng, không nhét vào text hoặc
predicate tùy ý.

Fact identity là fingerprint chuẩn hóa từ subject, predicate, object/value,
polarity, qualifiers, valid-time và branch scope; thứ tự key không ảnh hưởng
fingerprint. `claim_id` là định danh record, không tự quyết hai claim có cùng
fact hay không.

## Invariant

- Predicate chưa có schema không thể authoritative.
- Prose không reverse-extract thành canon.
- Fingerprint phải deterministic và có schema version.
- Mutation nào không ánh xạ được typed operation thì bị loại trước commit.
- Schema evolution phải có migration/ADR và không làm đổi lịch sử cũ âm thầm.

## Hệ quả

Guard, retrieval và replay có contract máy đọc được. Những chi tiết văn phong
không cần schema vẫn có thể tồn tại dưới dạng non-canonical narrative.
