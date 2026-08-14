# ADR-0009: Logical AI role và physical model call

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Planner, Simulator, Context Validator, Writer và Critic là năm contract logic.
Buộc mỗi role thành một request mạng riêng sẽ làm latency/cost tăng và không
phản ánh capability của model.

## Quyết định

Giữ năm logical role và cho phép Execution Planner tạo `PhysicalCallPlan`:

- Quality mặc định tách role để dễ trace và repair.
- Fast có thể fuse Planner + Simulator, hoặc Writer + Critic khi benchmark
  chứng minh không giảm chất lượng.
- Có thể skip/conditional Context Validator hoặc dùng model nhỏ theo risk score.

Fused call bắt buộc trả artifact riêng cho từng role và validate từng schema.
Trace bắt buộc ghi logical role, physical call ID, provider/model, fused roles,
skip reason, output contract và validator. Guard không bao giờ bị skip.

## Invariant

- Năm role không đồng nghĩa năm physical calls.
- Fuse không được gộp quyền authority hoặc bỏ artifact.
- Eval chấm logical role và physical call riêng.
- Mode không được đổi domain mutation contract.

## Hệ quả

Có thể tối ưu latency sau khi có baseline mà không redesign pipeline. Fast mode
không được coi là một đường tắt để bỏ validation deterministic.
