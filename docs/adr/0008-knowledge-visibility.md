# ADR-0008: Knowledge visibility qua observation, belief và evidence

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

Một event có thể là canon nhưng mỗi nhân vật chỉ biết phần họ trực tiếp thấy,
nghe, được kể hoặc suy ra. Một memory chung với `known_by` dễ làm lộ secret
hoặc future branch.

## Quyết định

Tách các lớp:

- `CanonFact`: điều thực sự đúng.
- `Event`: điều thực sự xảy ra.
- `Observation`: proposition một observer tiếp nhận từ event/source, có method,
  confidence, distortion và timestamp.
- `Belief`: proposition một believer tin với stance, confidence, evidence và
  counter-evidence; belief có thể sai.

Knowledge authorization bắt buộc hard-filter theo playthrough, branch ancestry,
fork boundary, time, owner/observer và entity trước keyword/vector ranking.
Một actor chỉ được hành động dựa trên claim nếu có observation/belief/evidence
đúng scope hoặc claim là public knowledge; policy của hành động có thể yêu cầu
confidence tối thiểu. Evidence link phải tồn tại.

Context của Simulator có thể chứa hidden state cần mô phỏng; Context Validator
và Writer chỉ nhận phần được phép. Player mode không nhận internal belief,
hidden goal hay numeric relationship nếu UI không cho phép.

## Invariant

- Vector search không bao giờ được dùng trước hard authorization filter.
- Observation của Alice không trở thành CanonFact chỉ vì Alice tin nó.
- Belief sai không sửa canon.
- Branch con không thấy future hoặc sibling record.
- Nếu evidence targeted chưa đủ, Validator trả `insufficient_evidence`, không
  mặc định PASS.

## Hệ quả

Memory có thể mô phỏng rumor, lời nói dối và hiểu lầm mà vẫn giữ một nguồn sự
thật. Retrieval trace phải lưu scope/filter để debug leak.
