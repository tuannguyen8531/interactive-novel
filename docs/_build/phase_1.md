# Báo cáo Phase 1 — Project skeleton

## 1. Mục tiêu của Phase

Theo docs/plan.md, Phase 1 phải tạo một ứng dụng backend/frontend còn rỗng nhưng có thể chạy, kiểm tra được và làm nền cho các phase sau. Phase này chỉ bao gồm skeleton, tooling, app factory, health check, frontend shell, typed transport contracts và architecture test; chưa triển khai persistence, domain engine hoặc provider.

## 2. Những gì đã thực hiện

- Hoàn thiện pyproject cho uv, build package bằng Hatchling, dependency groups dev và các cấu hình Ruff, Pyright, pytest.
- Pin dependency backend trong uv.lock; thêm FastAPI app factory, cấu hình Settings bằng pydantic-settings, CORS và lifecycle rỗng.
- Thêm endpoint GET /api/health với response typed và error envelope thống nhất cho application error, HTTP error, validation error và lỗi không xác định.
- Thêm các CLI entrypoint serve, test, build và migrate. migrate hiện là no-op có chủ đích vì persistence bắt đầu ở Phase 2.
- Tạo các package boundary tối thiểu src/domain, src/graph và src/services; thêm architecture tests kiểm tra dependency direction và import cycle.
- Khởi tạo Vue 3, TypeScript, Vite, Pinia, Vue Router, frontend shell và Home view.
- Thêm typed API client, auth token hook, fetch-based SSE abstraction có hỗ trợ Last-Event-ID, Pinia app store và UI health check.
- Thêm test backend cho health/error envelope và test frontend cho store thành công/lỗi.
- Cập nhật README và .gitignore cho workflow backend/frontend.

## 3. File/module quan trọng đã tạo hoặc thay đổi

Backend và tooling:

- pyproject.toml, uv.lock.
- src/config.py.
- src/api/factory.py, src/api/schemas.py, src/api/errors.py.
- src/api/routes/health.py.
- src/application/errors.py.
- src/cli/serve.py, src/cli/test.py, src/cli/build.py, src/cli/migrate.py.
- src/domain/__init__.py, src/graph/__init__.py, src/services/__init__.py.

Frontend:

- web/package.json, web/package-lock.json, web/vite.config.ts, web/vitest.config.ts.
- web/src/api/client.ts, web/src/api/sse.ts, web/src/api/types.ts.
- web/src/stores/app.ts, web/src/router/index.ts, web/src/App.vue, web/src/views/HomeView.vue, web/src/main.ts.

Tests và tài liệu:

- tests/api/test_health.py.
- tests/architecture/test_dependencies.py.
- web/src/stores/app.test.ts.
- README.md và báo cáo này.

## 4. Quyết định triển khai đáng chú ý

- Giữ namespace package là src, phù hợp với cấu trúc tham chiếu và import convention của novel-ai-trans.
- Dependency direction được khóa bằng test AST: api hướng vào application, graph hướng vào application contracts/domain policies, services là adapter hướng vào các port phía trong; domain không phụ thuộc FastAPI, SQLAlchemy, LangGraph hay provider SDK.
- Health route dùng async handler. Đây là lựa chọn nhỏ ở tầng transport để không phụ thuộc AnyIO worker thread trong môi trường local/sandbox; không làm thay đổi domain boundary.
- Error response dùng một envelope ổn định dạng error gồm code, message và details để frontend có thể xử lý nhất quán.
- SSE được đặt thành abstraction fetch-based, chưa gắn với job/persistence cụ thể. Last-Event-ID, auth token và AbortSignal đã được chừa sẵn cho Phase 10.
- Dev server frontend proxy /api tới backend tại 127.0.0.1:8000; production build chỉ tạo static assets.
- CLI migrate chỉ báo rằng migration bắt đầu từ Phase 2, tránh tạo persistence ngoài scope Phase 1.

## 5. Những phần tái sử dụng từ novel-ai-trans

Đã tái sử dụng theo chiến lược trong plan.md ở mức pattern và module boundary, không sao chép toàn bộ repository:

- Hình dạng tooling/CLI và app factory.
- Pattern error envelope và mapping lỗi ra HTTP response.
- Frontend shell Vue, router/store bootstrap.
- Typed API client và hướng thiết kế SSE client.
- Namespace src và cách tổ chức boundary package để giữ dependency direction.

Các phần database, domain engine, provider adapter, LangGraph pipeline và gameplay chưa được mang sang vì thuộc các phase sau.

## 6. Tests, lint và type-check

| Kiểm tra | Kết quả |
|---|---|
| uv run test | PASS — Ruff check, Ruff format, Pyright và pytest đều xanh; 5 tests passed |
| npm run test:unit | PASS — 1 file, 2 tests passed |
| npm run build | PASS — vue-tsc và Vite build thành công |
| uv run build | PASS — CLI build gọi frontend production build thành công |
| uv run migrate | PASS — no-op có chủ đích, chưa có migration ở Phase 1 |
| Browser UI health check | PASS — trang hiển thị Connected · 0.1.0; Check again gọi lại health thành công |
| git diff --check | PASS |

Backend đã được chạy bằng uv run serve và frontend bằng npm run dev -- --host 127.0.0.1 trong quá trình kiểm tra thực tế.

## 7. Tiêu chí hoàn tất

- PASS — Một lệnh chạy backend: uv run serve khởi động Uvicorn và phục vụ /api/health.
- PASS — Một lệnh chạy frontend: npm run dev -- --host 127.0.0.1 khởi động Vite.
- PASS — Health check từ UI thành công: Home view hiển thị Connected · 0.1.0 sau khi gọi backend.
- PASS — Lint, type-check và test xanh: uv run test, npm run test:unit và npm run build đều thành công.

## 8. Vấn đề, technical debt và blocker còn lại

- Không có blocker làm chặn việc hoàn tất Phase 1.
- Persistence, migration thật, domain model, provider contract và job/SSE backend chưa có; đây là phần cố ý để dành cho các phase tương ứng.
- npm install báo warning deprecation của glob nhưng audit kết thúc với 0 vulnerabilities; dependency này nên được xem xét khi nâng toolchain.
- Mẫu báo cáo nằm dưới docs/_build, vốn bị .gitignore bỏ qua; khi commit Phase 1 cần force-add báo cáo giống quy ước đã dùng cho Phase 0.

## 9. Những việc dự kiến của Phase tiếp theo nhưng CHƯA thực hiện

Phase 2 — Persistence foundation chưa được thực hiện. Các việc còn để dành gồm SQLAlchemy async/aiosqlite, PRAGMA, Alembic, schema worlds/playthroughs/branches/turns/characters/character_states, repository ports/adapters, Unit of Work, runtime path management và migration/repository contract tests.

## 10. Git diff, status và commit đề xuất

- Phase 0 đã được commit trước khi bắt đầu Phase 1 với mã 5e37d4b.
- git diff --check: PASS.
- Working tree hiện có thay đổi của .gitignore, README.md, pyproject.toml và các file mới trong src/, tests/, web/ cùng uv.lock và web/package-lock.json.
- Chưa chạy git commit hoặc git push cho Phase 1.
- Commit message đề xuất: feat: scaffold Phase 1 backend and frontend
