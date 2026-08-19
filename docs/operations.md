# Vận hành alpha

## Khởi động lần đầu

Từ thư mục dự án:

```bash
uv sync
uv run doctor
uv run migrate
uv run build
uv run serve
```

`doctor` chỉ tạo các thư mục runtime và kiểm tra readiness; nó không gọi
provider. Dữ liệu canonical nằm ở `runtime/game.db`, còn checkpoint LangGraph
nằm riêng ở `runtime/checkpoints.db`. Sau `uv run build`, backend phục vụ SPA
đã build tại `http://127.0.0.1:8000`; `/api`, `/docs` và `/openapi.json` vẫn là
các route backend riêng.

Khi phát triển giao diện với hot reload, dùng hai terminal:

```bash
# terminal 1
uv run serve

# terminal 2
cd web && npm run dev
```

Kiểm tra dự án theo cùng quy ước với `novel-ai-trans`:

```bash
uv run test
uv run test --frontend
```

Lệnh đầu chạy Ruff, Pyright và Pytest; cờ `--frontend` thêm Vue unit tests.
Nếu chạy trong sandbox và một API test không trả kết quả sau 30 giây, hãy dừng
lệnh từ môi trường chạy; đây không phải giới hạn của `uv run test` khi chạy
bên ngoài sandbox.

## Integrity và backup

Kiểm tra database:

```bash
uv run backup integrity
```

Tạo backup nhất quán qua SQLite online-backup API:

```bash
uv run backup create --output runtime/exports/game.db.backup
```

Khôi phục vào đường dẫn đã chỉ rõ:

```bash
uv run backup restore \
  --input runtime/exports/game.db.backup \
  --database runtime/game.db
```

Lệnh restore kiểm tra integrity của nguồn, ghi vào file tạm, kiểm tra file đích
rồi mới thay thế atomically. Hãy giữ một bản backup ngoài thư mục runtime trước
khi restore vào database đang dùng.

Export playthrough dạng JSON thường có ở `GET /api/playthroughs/{id}/export`.
Endpoint `.../export/bundle` thêm checksum; `POST /api/exports/validate` kiểm
tra checksum và scope trước khi một workflow import tiếp nhận dữ liệu. Import
không tự cấp authority cho prose; việc ghi canonical vẫn phải đi qua application
transaction.

## Provider, telemetry và bảo mật

- Provider lỗi được chuyển thành lỗi an toàn và không được làm mất canonical
  save; fallback chỉ chạy khi lỗi cho phép.
- Telemetry mặc định tắt. Chỉ khi đặt `TELEMETRY_ENABLED=true` mới tạo
  `runtime/logs/telemetry.jsonl`; file chỉ chứa latency, token counts, cost ước
  tính và provider metadata, không chứa prompt/output.
- `INTERACTIVE_NOVEL_DEBUG` mặc định tắt. Không đặt API key trong frontend,
  prompt, event SSE hoặc log.
- Input người chơi được giới hạn, chuẩn hóa và gắn nhãn untrusted; cờ prompt
  injection không biến input thành system/developer instruction.

## Alpha feedback loop

Người dùng có thể gửi rating/comment qua `POST /api/feedback`. Feedback được
giới hạn kích thước, redact secret phổ biến và ghi vào
`runtime/logs/feedback.jsonl`; đây là dữ liệu opt-in riêng, không phải memory
canon.

## Kiểm thử trong sandbox

Các test persistence/API có thể cần SQLite lifecycle hoặc provider thật. Khi một
test API/sandbox không trả kết quả trong 30 giây, dừng test đó, bỏ qua phần test
đã treo và ghi rõ trong báo cáo; không tải package mới khi chưa có phép.
