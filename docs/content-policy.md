# ContentPolicy schema và deterministic enforcement

Đây là policy contract cho World Builder, domain Guard, Writer và Critic. Nó
không được biểu diễn chỉ bằng prompt text.

## 1. Schema chuẩn hóa

```text
ContentPolicy {
  schema_version: string
  rating: teen_14_plus | mature_16_plus | adult_18_plus
  topic_boundaries: map<TopicTag, allow | opt_in | excluded>
  violence_ceiling: none | restrained | detailed
  adult_explicit_opt_in: bool
  consent: {
    required: bool
    explicit_affirmative: bool
    withdrawal_supported: bool
  }
  player_overrides: optional ContentPolicyOverride
}
```

Player override không phải policy độc lập có thể nới world. Effective policy
lấy giới hạn chặt hơn ở từng field; `excluded` không thể bị đổi thành allow
trong một turn. `adult_explicit_opt_in` chỉ có hiệu lực nếu world rating cũng là
`adult_18_plus`.

Topic boundary có thể dùng các tag sau trong MVP:

| Nhóm | Tag |
|---|---|
| Romance | `romantic_affection`, `dating`, `kiss`, `non_graphic_intimacy` |
| Mature | `mature_emotional_theme`, `sexual_reference_fade_to_black` |
| Adult | `adult_explicit`, `sexualized_nudity`, `fetishization` |
| Safety | `grooming`, `exploitation`, `non_consensual_sexual` |
| Violence | `violence`, `violence:torture`, `sexual_violence` |
| Sensitive | `psychological_harm`, `loss`, `complex_relationship` |

Tag mới phải có schema version, meaning, allowed rating và fixture. Không dùng
relationship score để suy ra consent hay adult eligibility.

## 2. Age gate tại scene

Age được tính tại `SceneSpec.world_time`, không tại thời điểm tạo World.

| Participant age | Allowed | Forbidden |
|---:|---|---|
| 14–15 | rung động, hẹn hò, nắm tay, ôm, hôn nhẹ, xung đột tình cảm | sexualization, explicit nudity, fetishization, sexual behavior |
| 16–17 | mature emotional themes, boundaries, jealousy, breakup, non-graphic intimacy | explicit sexual description; eroticized sexual activity |
| 18+ | adult themes/explicit chỉ khi tất cả gate khác pass | thiếu opt-in, thiếu consent, topic excluded, vượt violence ceiling |

Quan hệ giữa adult và minor không được trình bày như romance tích cực; grooming
và exploitation luôn bị deny. Timeskip không retroactively sửa decision hoặc
lịch sử scene cũ.

## 3. Consent state machine

Consent record có `scene_id`, participant, activity tag, state, requested_at,
decided_at, source/evidence và withdrawal metadata. Transition hợp lệ:

```text
not_discussed → requested
requested → granted | declined
granted → withdrawn
declined → requested
withdrawn → requested
```

`granted` phải là affirmative, activity-specific và có thể rút lại. Silence,
fear, intoxication, prior relationship, prior consent hoặc high attraction
không phải grant. Mỗi adult participant trong scene explicit phải có consent
record hợp lệ.

## 4. Violence ceiling và topic decision

`SceneSpec` biểu diễn loại nội dung và mức miêu tả ở hai field độc lập:

```text
content_tags: violence | violence:torture | sexual_violence | ...
violence_detail: none | restrained | detailed
```

Torture là subtype của violence. Sexual violence chịu violence ceiling đồng
thời vẫn có thể bị thắt chặt độc lập qua `topic_boundaries`.

| Nội dung cảnh | `none` | `restrained` | `detailed` |
|---|---:|---:|---:|
| Violence | deny | allow restrained | allow restrained/detailed |
| `violence:torture` | deny | allow restrained | allow restrained/detailed |
| `sexual_violence` | deny | allow restrained | allow restrained/detailed |

- `none`: không cho phép hành động hoặc hậu quả bạo lực được miêu tả.
- `restrained`: nội dung có thể xảy ra nhưng không có chi tiết thể chất sống
  động, máu me, giải phẫu hoặc quá trình gây đau đớn kéo dài.
- `detailed`: cho phép miêu tả trực diện hành động và hậu quả thể chất.
- `topic_boundaries.* = excluded` luôn deny bất kể ceiling.
- Provider refusal không được fallback để lách policy; chỉ retry với request
  hợp lệ hoặc downgrade rõ ràng.

Loader tiếp tục nhận `non_graphic` và `graphic` từ world cũ, sau đó chuẩn hóa
thành `restrained` và `detailed`.

## 5. Deterministic evaluation order

Guard đánh giá theo thứ tự và dừng ở lỗi không thể downgrade:

1. Schema/tag/participant/reference tồn tại.
2. Tính age của từng participant tại world time.
3. Chặn adult/minor romance và explicit content không hợp tuổi.
4. Kiểm violence ceiling từ loại nội dung và mức miêu tả của scene.
5. Kiểm topic boundaries và effective player policy.
6. Kiểm rating, explicit opt-in và consent cho activity adult.
7. Nếu beat còn hợp lệ sau khi bỏ mức mô tả cấm, trả `downgrade` kèm SceneSpec
   an toàn; ngược lại trả `deny`.

Output tối thiểu:

```text
PolicyDecision {
  decision: allow | downgrade | deny
  reason_codes: list<string>
  effective_policy_version: string
  participant_ages: map<id, int>
  evaluated_tags: list<TopicTag>
  evaluated_world_time: int
}
```

## 6. Enforcement points

1. World Builder validate tuổi, rating, warnings, boundaries và initial scene.
2. Planner/Simulator nhận policy như constraint bắt buộc.
3. Claim Extractor gắn participant/age/consent/content tags.
4. Guard quyết định deterministic trước SceneSpec.
5. Writer chỉ nhận tags/mức mô tả đã allow.
6. Critic tìm tag/chi tiết vượt policy ở draft cuối; Critic không cấp quyền
   canon và không override Guard.

Fixture executable-design nằm tại `tests/fixtures/scenarios/content_policy.json`;
deterministic Guard tests chạy trực tiếp từ fixture này và từ ma trận subtype ×
violence ceiling.
