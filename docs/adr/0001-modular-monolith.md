# ADR-0001: Modular monolith và hướng phụ thuộc

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

MVP cần một canonical transaction cho một lượt chơi, chạy local-first và dễ
debug. Tách microservice sớm sẽ làm transaction, checkpoint, cancellation và
branch consistency khó kiểm tra hơn mà chưa đem lại lợi ích cần thiết.

## Quyết định

Xây một modular monolith Python. Ranh giới module được kiểm tra bằng
architecture tests và không phụ thuộc vào cách deploy hiện tại.

Hướng phụ thuộc bắt buộc:

```text
api → application → domain
graph → application contracts + domain policies
services → implements ports declared inward
domain → không import FastAPI, SQLAlchemy, LangGraph hoặc provider SDK
```

`api` và `cli` là adapter mỏng. `application` sở hữu use case và transaction
boundary. `domain` sở hữu invariant thuần. `graph` điều phối các contract; nó
không trở thành nơi sở hữu sự thật. `services` hiện thực port persistence,
LLM, embedding và logging được khai báo ở lớp hướng vào.

## Invariant

- Domain không import framework, ORM, LangGraph hoặc provider.
- API không trả ORM model trực tiếp.
- Một use case ghi dữ liệu không tự ý mở transaction thứ hai ở adapter.
- Không thêm microservice, broker hoặc worker phân tán trong MVP.
- Architecture test phải bắt import ngược và import cycle.

## Hệ quả

Một process có thể dùng SQLite transaction nguyên tử và chạy offline. Khi cần
PostgreSQL hoặc worker riêng, chỉ adapter và deployment thay đổi; domain,
application contract và canonical semantics không đổi.

## Không thuộc quyết định này

Không khóa UI component library, cơ chế scale nhiều user, hay hạ tầng
production phân tán.
