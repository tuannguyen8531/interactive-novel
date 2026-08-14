# Architecture Decision Records

Các ADR trong thư mục này là quyết định đã khóa cho MVP. Một thay đổi làm
ảnh hưởng đến ownership của state, quyền biết, canonical transaction, branch
semantics, content policy hoặc dependency direction phải tạo ADR mới hoặc
supersede ADR cũ; không sửa âm thầm quyết định đã dùng trong dữ liệu.

| ADR | Quyết định |
|---|---|
| [0001](0001-modular-monolith.md) | Modular monolith và hướng phụ thuộc |
| [0002](0002-sqlite-mvp.md) | SQLite cho MVP |
| [0003](0003-event-current-state-snapshot.md) | Event log, current state và snapshot |
| [0004](0004-langgraph-boundary.md) | LangGraph chỉ orchestration/checkpoint |
| [0005](0005-direct-provider-adapters.md) | Provider adapter REST trực tiếp |
| [0006](0006-directed-relationships.md) | Quan hệ có hướng, nhiều chiều |
| [0007](0007-knowledge-proposition-model.md) | Typed proposition, fact identity và predicate registry |
| [0008](0008-knowledge-visibility.md) | Visibility qua observation/belief/evidence |
| [0009](0009-logical-role-physical-call.md) | Logical AI role và physical model call |
| [0010](0010-canonical-derived-lifecycle.md) | Vòng đời canonical và derived data |
| [0011](0011-offscreen-simulation-boundary.md) | Ranh giới mô phỏng ngoài camera |
| [0012](0012-content-policy-enforcement.md) | ContentPolicy và enforcement đa tầng |
| [0013](0013-branch-semantics.md) | Semantics của branch, fork và regenerate |
| [0014](0014-relationship-scale.md) | Domain thang đo và update policy quan hệ |
| [0015](0015-in-world-clock.md) | Đồng hồ trong truyện |

Trạng thái của toàn bộ ADR: **Accepted for MVP**.
