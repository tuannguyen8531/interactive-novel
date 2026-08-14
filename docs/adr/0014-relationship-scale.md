# ADR-0014: Domain thang đo và update policy quan hệ

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Một công thức `new = old + delta` cho mọi metric khiến trust, fear và
familiarity biến động phi lý. Engine cần domain rõ để Guard và property test.

## Quyết định

Domain canonical của từng dimension:

| Dimension | Domain | Ghi chú |
|---|---:|---|
| affection | `[-1, 1]` | warm appraisal ↔ aversion |
| attraction | `[0, 1]` | romantic/physical pull, không phải affection |
| trust | `[0, 1]` | tăng chậm, betrayal có thể giảm mạnh |
| respect | `[-1, 1]` | admiration ↔ contempt |
| comfort | `[0, 1]` | safety/context/familiarity |
| fear | `[0, 1]` | threat-dependent, có decay |
| resentment | `[0, 1]` | decay chậm, grievance củng cố |
| familiarity | `[0, 1]` | engine-derived, gần monotonic |

API/debug map appraisal sang `0–100` bằng `(value + 1) / 2 * 100` và intensity
sang `value * 100`; map này không phải domain lưu trữ.

Mỗi policy chốt evidence/event types hợp lệ, max delta mỗi turn, asymmetry,
decay, saturation/diminishing return, trait modifier và hysteresis. Simulator
chỉ đề xuất; deterministic engine áp dụng. `familiarity` tính từ shared scenes,
conversations, meaningful events và elapsed relationship duration.

## Invariant

- Không dimension nào vượt domain sau apply/replay.
- Attraction không tự suy ra affection hoặc commitment.
- Hành động tử tế bình thường không mặc định tăng romance.
- Label hysteresis không được làm đổi canonical vector.
- Dependency/reliance không nằm trong core vector MVP.

## Hệ quả

Property tests có thể chứng minh range; scenario eval có thể đo proportionality,
romantic escalation và resistance mà không dựa vào label mơ hồ.
