# Scenario fixture contract

Các file trong thư mục này là design data của Phase 0, không gọi LLM và không
ghi database. Mỗi scenario phải có:

- `id`, `category`, `setup`, `actions` hoặc `stimulus`;
- `expected_invariants` mô tả assertion bắt buộc;
- `hard_failures` là lỗi không được phép xuất hiện;
- `implementation_phase` cho biết Phase nào parameterize fixture thành test.

`core_acceptance.json` dùng cho deterministic engine, repository/branch và
scenario eval. `claim_contracts.json` khóa mapping từ AI proposal sang typed
claim/operation. `content_policy.json` là vector deterministic cho
`ContentPolicy`. `reference_matrix.json` khóa metadata cần ghi khi đo quality,
latency và cost; các số đo thật bắt đầu ở Phase 3 và phải giữ dataset/prompt/
model/config version.

Fixture không phải canon của một world cụ thể. ID trong fixture là stable test
IDs và mỗi test phải tạo namespace playthrough/branch riêng.
