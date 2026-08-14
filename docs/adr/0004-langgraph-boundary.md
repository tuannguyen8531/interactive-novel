# ADR-0004: LangGraph chỉ orchestration và checkpoint

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Turn pipeline cần resume, conditional repair và trace, nhưng game save phải
độc lập với trạng thái tạm của một lần chạy model.

## Quyết định

LangGraph chỉ điều phối các node và lưu checkpoint thực thi. `TurnGraphState`
là bounded state của một `turn_run_id`, không chứa ORM session, toàn bộ lịch sử
hay game state không cần cho run. Checkpoint dùng thread ID bằng
`turn_run_id`, không dùng `playthrough_id` hoặc `branch_id`.

Game save chỉ được tạo qua Canonical Record Builder và application commit
service vào `game.db` theo ADR-0010.

## Invariant

- Resume checkpoint không được double-commit canonical turn.
- Mất checkpoint không làm mất turn đã commit.
- Checkpoint không thay thế event log/current state/snapshot.
- Node không được tự ý ghi canonical state ngoài commit boundary.

## Hệ quả

Có thể thay LangGraph hoặc chạy fake pipeline trong test mà không đổi domain
save semantics. Checkpoint cleanup và game save retention có vòng đời riêng.

## Không làm trong MVP

Không để LangGraph sở hữu transaction sản phẩm hoặc dùng graph state làm API
response model.
