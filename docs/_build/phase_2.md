# Báo cáo Phase 2 — Persistence foundation

## 1. Mục tiêu của Phase

Theo docs/plan.md, Phase 2 phải cung cấp nền persistence local-first để schema và repository có thể lưu/load dữ liệu cơ bản. Phase này phải giữ transaction boundary ở application, dùng SQLite canonical game database, có migration lặp lại được, và không đưa SQLAlchemy hoặc infrastructure dependency vào domain.

## 2. Những gì đã thực hiện

- Thêm SQLAlchemy async, aiosqlite và Alembic vào pyproject.toml; uv.lock đã resolve các phiên bản SQLAlchemy 2.0.52, aiosqlite 0.22.1 và Alembic 1.19.1.
- Thêm runtime path management tại src/paths.py, anchored mặc định vào runtime/ trong project root; hỗ trợ game.db, checkpoints.db, logs, exports và override root cho test/deployment.
- Thêm Database factory dùng AsyncEngine/AsyncSession với SQLite PRAGMA foreign_keys=ON, journal_mode=WAL và busy_timeout có cấu hình.
- Khởi tạo Alembic, async migration environment và revision 0001_initial_persistence.
- Tạo sáu nhóm schema theo plan: worlds, playthroughs, branches, turns, characters và character_states, với UUID TEXT, UTC audit timestamps, JSON payload thưa, lifecycle checks, unique constraints và foreign keys.
- Tạo persistence-neutral WorldRecord và PlaythroughRecord ở application contracts; chưa biến chúng thành full domain entities của Phase 3.
- Tạo WorldRepository, PlaythroughRepository và UnitOfWork ports ở application; tạo SQLAlchemy repositories và UnitOfWork adapter ở services.
- Tạo WorldApplicationService và PlaythroughApplicationService cho create/load; playthrough creation kiểm tra world tồn tại trong cùng application transaction.
- Cập nhật CLI migrate để chạy Alembic head, hỗ trợ override database path và dùng runtime/game.db mặc định.
- Mở rộng architecture test để cho phép services chỉ phụ thuộc inward application contracts/ports, đồng thời vẫn cấm phụ thuộc api/cli/graph.
- Thêm migration smoke test từ database rỗng, runtime path test, repository round-trip test, foreign-key failure test và rollback test.
- Cập nhật README và .gitignore cho database runtime workflow.

## 3. File/module quan trọng đã tạo hoặc thay đổi

Runtime và migration:

- alembic.ini.
- alembic/env.py, alembic/script.py.mako.
- alembic/versions/0001_initial_persistence.py.
- src/paths.py.
- src/services/persistence/database.py, models.py, migrations.py.

Application boundary và adapter:

- src/application/contracts/persistence.py.
- src/application/ports/persistence.py.
- src/application/services/worlds.py, playthroughs.py.
- src/services/persistence/repositories.py, uow.py.
- src/cli/migrate.py, src/config.py.

Tests và tài liệu:

- tests/persistence/conftest.py.
- tests/persistence/test_migrations.py.
- tests/persistence/test_repositories.py.
- tests/architecture/test_dependencies.py.
- README.md, pyproject.toml, uv.lock và báo cáo này.

## 4. Quyết định triển khai đáng chú ý

- game.db là canonical product database; checkpoints.db chỉ được dành riêng cho LangGraph execution state, đúng ADR-0002 và không được dùng làm save game.
- SQLAlchemy model và SQLite-specific code chỉ nằm trong services/persistence. Application chỉ nhìn thấy records, repository ports và UnitOfWork protocol; domain vẫn không import ORM/framework.
- UnitOfWork tạo một AsyncSession và một transaction cho mỗi use case. Commit do application service gọi; exception hoặc use case không commit sẽ rollback khi context đóng.
- aiosqlite PRAGMA được cài qua async bridge run_async của SQLAlchemy event để không deadlock worker thread. Kiểm chứng thực tế cho kết quả foreign_keys=1, journal_mode=wal và busy_timeout=5000.
- Schema bao gồm các foreign key vòng qua playthrough/character/branch/turn dưới dạng nullable bootstrap references; điều này cho phép tạo aggregate theo nhiều bước mà vẫn giữ referential integrity. Các invariant head/fork/player/root chặt hơn sẽ thuộc use case/domain contract ở các phase sau.
- JSON chỉ dùng cho payload cấu hình/trạng thái thưa; UUID và audit timestamp giữ đúng quy ước domain model. Không lưu raw prompt/output hay event log đầy đủ ở Phase 2.
- Migration được chạy qua Alembic API với connection async đã mở, nên cùng một runner dùng được trong CLI và async test fixture; lần upgrade thứ hai là no-op.
- Settings tránh va chạm với biến môi trường hệ thống DEBUG=release bằng alias INTERACTIVE_NOVEL_DEBUG cho field debug.

## 5. Những phần tái sử dụng từ novel-ai-trans

- Tái sử dụng ý tưởng từ ../novel-ai-trans/src/paths.py: project-root anchoring, runtime root có thể override, các helper trả path ổn định và tạo thư mục khi cần.
- Tái sử dụng cách tổ chức CLI/tooling và test fixture theo pattern của repository tham chiếu, nhưng viết lại cho game.db/checkpoints.db và bỏ toàn bộ translation/import assumptions.
- Không có persistence ORM/migration contract phù hợp trong novel-ai-trans để copy trực tiếp; schema, ports, UoW và migration của interactive-novel được thiết kế mới theo ADR/plan.
- Không copy toàn bộ repository tham chiếu.

## 6. Tests, lint và type-check

| Kiểm tra | Kết quả |
|---|---|
| uv run test | PASS — ruff check, ruff format, pyright và pytest đều xanh |
| pytest trực tiếp | PASS — 10 tests passed |
| Migration smoke test | PASS — database rỗng upgrade được hai lần; schema và alembic_version đúng |
| Repository contract tests | PASS — World/Playthrough create-load round-trip và missing-world diagnostic |
| Rollback test | PASS — insert World trước lỗi foreign key của Playthrough không để lại World dở |
| Foreign key/PRAGMA test | PASS — foreign_keys=1, WAL và busy_timeout=5000 |
| uv run migrate --database ... | PASS — CLI upgrade database rỗng |
| uv run build | PASS — frontend type-check và Vite production build |
| git diff --check | PASS trên tracked diff; new files không có trailing whitespace |

Các test có aiosqlite được chạy ngoài sandbox vì môi trường sandbox hiện treo worker thread của aiosqlite; cùng test suite chạy thành công trong môi trường escalated bình thường.

## 7. Tiêu chí hoàn tất

- PASS — Create/load một World và Playthrough qua application service: WorldApplicationService và PlaythroughApplicationService được kiểm chứng bằng round-trip repository test.
- PASS — Rollback thực sự không để dữ liệu dở: lỗi foreign key trong cùng UnitOfWork rollback World đã flush trước đó; query sau transaction không thấy bản ghi.
- PASS — Foreign keys hoạt động: PRAGMA foreign_keys được bật trên connection và invalid Playthrough bị IntegrityError.
- PASS — Migration từ database rỗng chạy được nhiều lần trong test fixture: lần đầu tạo đủ sáu nhóm schema, lần hai không tạo revision mới; CLI cũng đã chạy lặp thành công.

## 8. Vấn đề, technical debt và blocker còn lại

- Không có blocker làm chặn việc hoàn tất Phase 2.
- Giới hạn môi trường: sandbox không phù hợp với worker thread của aiosqlite; đây không phải lỗi runtime khi chạy ngoài sandbox, nhưng cần giữ lưu ý trong CI/local test runner.
- Repository adapter hiện tập trung vào World và Playthrough vì đó là acceptance path của Phase 2. Repository cho Branch, Turn, Character và CharacterState sẽ được bổ sung khi application/domain contracts tương ứng xuất hiện.
- Migration đầu tiên đã tạo foundational tables nhưng chưa có event log, snapshot, claims, relationships, outbox hay replay tables; các phần đó thuộc Phase 3/4 và không được mở rộng vào Phase này.
- Runtime database trong runtime/ bị .gitignore bỏ qua; dữ liệu local không thuộc source control.

## 9. Những việc dự kiến của Phase tiếp theo nhưng CHƯA thực hiện

Phase 3 — Pure domain engine chưa được thực hiện. Các việc còn để dành gồm value objects/entities, InWorldClock rules, CharacterProfile/State đầy đủ, relationship policies, psychological state, ContentPolicy/consent, KnowledgeClaim/CanonFact, Event/Observation/Belief/Evidence, StatePatch, deterministic State Guard, knowledge authorization và apply/revert/replay in-memory.

Phase 4 event log, snapshot và branching cũng chưa được thực hiện; không được kéo vào Phase 2.

## 10. Git diff, status và commit đề xuất

- Phase 0 commit: 5e37d4b — docs: establish Phase 0 architecture and acceptance contracts.
- Phase 1 commit: 253feaf — feat: scaffold Phase 1 backend and frontend.
- HEAD hiện là 253feaf; Phase 2 chỉ đang ở working tree, chưa stage, chưa commit và chưa push.
- git diff --check: PASS.
- git status gồm các file modified ở .gitignore, README.md, pyproject.toml, src/config.py, src/cli/migrate.py, tests/architecture/test_dependencies.py, uv.lock và các file mới dưới alembic/, src/application/contracts, src/application/ports, src/application/services, src/paths.py, src/services/persistence và tests/persistence.
- Báo cáo này nằm dưới docs/_build, bị .gitignore bỏ qua; khi commit Phase 2 cần force-add báo cáo.
- Commit message đề xuất: feat: add Phase 2 persistence foundation.
