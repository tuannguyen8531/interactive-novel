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
uv run test --no-frontend
```

Mặc định lệnh chạy Ruff, Pyright, Pytest và Vue unit tests; cờ
`--no-frontend` chỉ bỏ qua Vue unit tests khi cần kiểm tra riêng backend.
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
tra checksum và scope. `POST /api/exports/import` thực hiện exact restore một
bundle đã ký checksum bằng cách tái dựng opening records và replay từng typed
patch qua canonical commit. Import từ chối ID đang tồn tại; hãy xóa world cũ
trước khi restore đúng bundle đó. UI tương ứng nằm trong **Data → Import bundle**.

Trang **Data** cũng cho phép tạo/list/restore backup. API chỉ chấp nhận tên file
an toàn bên trong `runtime/exports`, không nhận đường dẫn filesystem tùy ý. Khi
restore, turn workers được dừng, connection pool được đóng, file được thay thế
atomically rồi workers mới chạy lại.

## Provider, telemetry và bảo mật

- Provider lỗi được chuyển thành lỗi an toàn và không được làm mất canonical
  save; fallback chỉ chạy khi lỗi cho phép.
- Telemetry mặc định tắt. Chỉ khi đặt `TELEMETRY_ENABLED=true` mới tạo
  `runtime/logs/telemetry.jsonl`; file chỉ chứa latency, token counts, cost ước
  tính và provider metadata, không chứa prompt/output.
- Mọi provider call được ghi riêng theo ngày vào
  `runtime/logs/YYYY-MM-DD/request.log`, `response.log` và `error.log`, tương tự
  `novel-ai-trans`. Request/response chứa đầy đủ payload gửi tới và nhận từ
  provider; credentials và query string vẫn được che. Log có thể chứa nội
  dung truyện riêng tư, vì vậy cần kiểm tra trước khi chia sẻ. Số ngày
  giữ log do `LOG_RETENTION_DAYS` điều khiển (mặc định 30).
- `INTERACTIVE_NOVEL_DEBUG` và `VITE_ENABLE_INSPECTOR` mặc định tắt. Muốn
  dùng Inspector phải bật backend, sau đó build frontend với cờ Vite.
  Không đặt API key trong frontend,
  prompt, event SSE hoặc log.
- Input người chơi được giới hạn, chuẩn hóa và gắn nhãn untrusted; cờ prompt
  injection không biến input thành system/developer instruction.

## Alpha feedback loop

Người dùng có thể gửi rating/comment qua `POST /api/feedback`. Feedback được
giới hạn kích thước, redact secret phổ biến và ghi vào
`runtime/logs/feedback.jsonl`; đây là dữ liệu opt-in riêng, không phải memory
canon.

Form tương ứng nằm trong trang **Data**.

## Quality gates và benchmark

- Frontend fixture acceptance chạy 30 lượt trong Vitest.
- Persistence soak commit/replay 100 lượt và kiểm tra branch head/invariants.
- Memory gate chạy 100 lượt, kiểm tra cả consolidation lẫn critical-memory
  Recall@5 = 1.00 qua nhiều cửa sổ thời gian.
- Canonical failure injection chạy qua từng bước của transaction và xác nhận
  rollback không để lại partial turn.
- `uv run quality-report` tổng hợp telemetry provider thật theo turn. Báo cáo
  không giả lập số liệu khi telemetry chưa có sample.

Browser E2E bằng Playwright hiện được chủ động hoãn để tránh thêm browser binary
và dependency nặng; API integration, Vue store acceptance và production build
vẫn nằm trong validation mặc định.

Gate 30 lượt hiện chứng minh luồng tương tác và state không thoái hóa.
Chất lượng văn phong/narrative của model là gate theo môi trường: cần
khóa provider, model và hardware trước khi ghi baseline, không suy ra từ
fixture deterministic.

## Kiểm thử trong sandbox

Các test persistence/API có thể cần SQLite lifecycle hoặc provider thật. Khi một
test API/sandbox không trả kết quả trong 30 giây, dừng test đó, bỏ qua phần test
đã treo và ghi rõ trong báo cáo; không tải package mới khi chưa có phép.
