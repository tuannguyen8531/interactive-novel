# ADR-0002: SQLite cho MVP

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Ứng dụng single-player, local-first và cần transaction rõ ràng hơn là thông
lượng multi-user. SQLite giảm chi phí vận hành và phù hợp với replay/event log.

## Quyết định

`game.db` là database canonical của sản phẩm; `checkpoints.db` là database
riêng cho LangGraph checkpoint. Dùng SQLAlchemy 2 async, `aiosqlite` và
Alembic làm nguồn migration duy nhất.

Khi mở connection, bắt buộc bật:

- `PRAGMA foreign_keys = ON`.
- WAL journal mode.
- `busy_timeout` có cấu hình.

UUID domain lưu dạng TEXT, timestamp lưu UTC, enum lưu text có validation và
JSON chỉ dành cho payload thưa có version. Một branch chỉ có một active turn;
WAL không được xem là cơ chế giải quyết mọi concurrency.

## Invariant

- Không dùng checkpoint DB làm save game.
- Không viết SQL SQLite rải trong application/domain.
- Mọi schema change qua Alembic.
- Foreign key và unique/idempotency constraint là một phần contract.
- Persistence port phải portable sang PostgreSQL.

## Hệ quả

MVP có thể chạy không cần dịch vụ ngoài và dễ tạo fixture database tạm. Khi
có nhiều process ghi, lock contention, replication hoặc multi-user, sẽ dựng
PostgreSQL từ cùng repository contract và migration path; đó là quyết định mới.

## Không làm trong MVP

Không thêm PostgreSQL vận hành thật, Redis, Celery, broker hay vector database.
