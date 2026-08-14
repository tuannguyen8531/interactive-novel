# ADR-0006: Quan hệ có hướng và nhiều chiều

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Quan hệ A → B không đồng nhất với B → A. Một scalar hoặc một label không biểu
diễn được tin cậy, sợ hãi, thoải mái, oán giận và tình cảm một phía.

## Quyết định

Lưu directed edge cho từng cặp character và vector các dimension:

`affection`, `attraction`, `trust`, `respect`, `comfort`, `fear`, `resentment`
và `familiarity`.

Mỗi dimension có policy riêng về evidence, delta tối đa, gain/loss asymmetry,
decay, saturation, trait modifier và hysteresis. Simulator chỉ đề xuất delta;
engine mới validate, clamp, apply policy và ghi `RelationshipChange` có
provenance. `familiarity` do engine suy ra từ shared exposure, meaningful
events và thời gian; LLM không ghi trực tiếp.

Jealousy không nằm trong vector. Nó là `EmotionalTension` ba ngôi gồm
observer, rival, focus, trigger, intensity, appraisal, decay và visibility.

## Invariant

- Không đảo chiều hoặc gộp hai directed edge.
- Label như friend, crush, lover là derived, không thay vector.
- `lover` cần commitment event phù hợp, không chỉ threshold.
- Không có dependency scalar trong core MVP.
- Mọi change có before, proposed delta, validated delta, after, cause và
  LLM provenance.

## Hệ quả

Engine giữ được agency và tình cảm một phía; UI có thể hiển thị nhãn mơ hồ
trong player mode và số liệu trong developer mode.
