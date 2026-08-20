# Kế hoạch xây dựng AI-powered VN/RPG Engine

> Trạng thái triển khai (2026-08-20): alpha feature set của Phase 1–14 đã được
> ghép vào một modular monolith; xem `docs/status.md` để biết mục nào đã kiểm
> chứng, mục nào còn phụ thuộc provider-real. Tài liệu này là roadmap/thiết kế,
> không còn là bảng tiến độ thực thi.
>
> Revision: đã tích hợp architectural review trước Giai đoạn 1, gồm typed knowledge propositions, targeted consistency retrieval, logical-role/physical-call separation, canonical/derived lifecycle, relationship policies, gameplay eval và off-screen simulation boundary.
>
> Phạm vi hiện tại: visual novel/RPG kể chuyện tương tác bằng văn bản, single-player, ưu tiên chạy local-first.
>
> Quyết định đã chốt: Python + uv, FastAPI, LangGraph, SQLite, Vue 3; LLM qua Ollama, Gemini và OpenRouter; chưa tích hợp OpenAI trực tiếp trong MVP.
>
> Phê duyệt trước Phase 0: product charter, MVP/non-goals, stack/provider, thứ tự ưu tiên, chính sách nội dung sơ bộ và Phase 0 exit gate đều đã được duyệt.

## 1. Tầm nhìn sản phẩm

Dự án là một narrative simulation engine có giao diện kiểu visual novel, không phải một chatbot chỉ nối tiếp văn bản.

Người chơi có thể:

- Mô tả bối cảnh, mẫu nhân vật lý tưởng, sắc thái câu chuyện và giới hạn nội dung.
- Để AI tạo world seed, dàn nhân vật, quan hệ ban đầu, bí mật, mục tiêu và xung đột.
- Nhập bất kỳ hành động hoặc lời thoại nào thay vì chọn A/B/C.
- Tạo ra diễn biến khác nhau dựa trên hành động, khả năng của nhân vật, thông tin họ thực sự biết và trạng thái thế giới.
- Có một kết thúc riêng cho từng playthrough mà không phụ thuộc vào các route và flag viết tay cứng nhắc.
- Lưu, tải, hoàn tác, tái sinh một lượt và rẽ nhánh từ bất kỳ điểm hợp lệ nào.

Mục tiêu cốt lõi là tạo cảm giác:

1. Nhân vật có đời sống nội tâm và hành vi nhất quán.
2. Thế giới phản ứng có nguyên nhân, không chiều theo người chơi vô điều kiện.
3. Chi tiết nhỏ đã xuất hiện có thể được nhớ lại đúng lúc.
4. Mỗi lựa chọn để lại hậu quả quan sát được lên con người, quan hệ và tuyến truyện.
5. Văn phong liền mạch nhưng sự thật không bị thay đổi tùy hứng bởi Writer.

## 2. Luận điểm kiến trúc trung tâm

### 2.1. LLM không phải cơ sở dữ liệu

LLM đảm nhiệm hiểu ý định, đề xuất diễn biến, mô phỏng tâm lý, viết văn và phê bình. Engine nắm quyền quyết định sự thật.

Ba lớp trách nhiệm:

| Lớp | Trách nhiệm |
|---|---|
| LLM | Hiểu, suy luận, đề xuất, diễn đạt |
| Domain engine | Kiểm tra quy tắc, chuẩn hóa, giới hạn thay đổi, tính trạng thái dẫn xuất |
| Persistence | Ghi lại sự thật, lịch sử, nhánh, phiên bản và provenance |

### 2.2. Ý định không đồng nghĩa với kết quả

Nếu người chơi nhập “tôi hạ gục hội trưởng trong một đòn”, đó chỉ là PlayerIntent. Planner và Simulator phải xét năng lực, hoàn cảnh, mục tiêu NPC, quan hệ, xác suất và giới hạn thế giới trước khi tạo kết quả.

### 2.3. Văn xuôi không có quyền tạo canon

Writer chỉ được viết từ SceneSpec đã duyệt. Nếu Writer thêm một chi tiết chưa được chấp thuận, chi tiết đó không tự động trở thành canon.

### 2.4. Không có route cứng vẫn cần state có cấu trúc

“Không flag định sẵn” không có nghĩa là không có trạng thái. Hệ thống vẫn cần các số đo quan hệ, mục tiêu, beliefs, narrative threads và các sự kiện. Khác biệt là chúng được cập nhật động từ diễn biến thay vì phục vụ một route viết trước.

### 2.5. LangGraph state không phải Game State

- LangGraph state: dữ liệu tạm thời của một lần chạy pipeline.
- Game State: trạng thái bền vững đã commit của playthrough/branch.
- LangGraph checkpoint: phục hồi tiến trình xử lý khi lỗi hoặc gián đoạn.
- Game snapshot/event log: phục hồi và tái dựng thế giới.

Không dùng checkpoint của LangGraph làm save game chính.

### 2.6. Canonical turn phải commit nguyên tử

Những dữ liệu có thẩm quyền của một lượt phải thành công cùng nhau hoặc rollback cùng nhau:

- Turn và final narrative.
- Events.
- State changes.
- Canon facts/typed claims được chấp thuận.
- Observations và beliefs.
- Relationship/tension changes.
- Thread/hook changes.
- Branch head và revision.

Derived data không được làm thất bại canonical transaction:

- Embeddings.
- Retrieval index.
- Episodic/narrative summaries có thể tái dựng.
- Consolidation.
- Analytics.

Sau canonical commit, outbox/derived jobs xử lý những dữ liệu này. Khi derived artifact chưa sẵn sàng, lượt sau fallback về raw/recent events và current state.

### 2.7. Mọi thay đổi có thẩm quyền phải biểu diễn được bằng typed domain claim

Invariant nền tảng:

> Every AI-proposed fact or state mutation must be representable as a typed domain claim before it can become authoritative.

Nói cách khác, một câu văn tự do như “Yuki có lẽ thích Akira” không thể trực tiếp trở thành canon hoặc belief. Nó phải được chuẩn hóa thành proposition/claim có subject, predicate, object/value, scope và provenance để engine có thể kiểm tra quyền biết, mâu thuẫn và bằng chứng.

### 2.8. Logical AI role không đồng nghĩa physical LLM call

Năm vai trò Planner, Simulator, Context Validator, Writer và Critic là năm contract logic, không phải cam kết gọi mạng đúng năm lần:

~~~text
5 logical roles ≠ 5 mandatory model calls
~~~

Runtime được phép batch, fuse, chạy local hoặc bỏ qua có điều kiện một physical call, miễn là:

- Output contract của từng role vẫn tách biệt và validate độc lập.
- Trace cho biết role nào được model/call nào thực hiện.
- Guard không bao giờ bị bỏ.
- Chất lượng được chứng minh bằng eval thay vì giả định.

### 2.9. Ranh giới mô phỏng ngoài camera

MVP không chạy autonomous simulation liên tục cho toàn bộ NPC ngoài camera. Thế giới chỉ materialize thay đổi ngoài màn hình khi:

- Có ScheduledEvent đã được khai báo.
- NarrativeThread yêu cầu tiến triển.
- Thay đổi trở nên liên quan trực tiếp tới scene hiện tại.

Mọi thay đổi vẫn cần nguyên nhân, typed claim/event và timestamp. WorldScheduler, NPCAgenda và WorldTick đầy đủ là subsystem hậu MVP.

### 2.10. Thứ tự ưu tiên đã phê duyệt

Khi hai mục tiêu xung đột, ưu tiên theo thứ tự:

1. Không mất, hỏng hoặc ghi sai dữ liệu.
2. Không rò bí mật/tri thức giữa nhân vật, lượt chơi hoặc branch.
3. Nhất quán nhân vật, quan hệ, thời gian và nhân quả.
4. Gameplay có agency, resistance và khả năng thất bại.
5. Chất lượng văn phong.
6. Latency.
7. Chi phí.

Không chấp nhận một bản văn hay hơn nếu nó phá canon hoặc knowledge boundary.

### 2.11. Nền tảng và privacy defaults đã phê duyệt

- Linux là nền tảng phát triển chính.
- Desktop browser là client đầu tiên.
- Runtime mặc định local, single-user.
- Ollama là tùy chọn; app vẫn khởi động khi Ollama chưa chạy.
- Cloud API dùng key của người dùng.
- API keys ưu tiên environment hoặc OS keyring, không trả lại client sau khi nhập.
- Tự động chuyển nội dung từ local provider sang cloud phải được người dùng bật rõ ràng; mặc định không gửi ra ngoài máy.

## 3. Phạm vi MVP

### 3.1. Có trong MVP

- Single-player, text-first.
- Một template đầu tiên: school romance.
- 2–4 NPC chính trong một playthrough.
- World Builder từ mô tả tự nhiên, sau đó cho người dùng xem và sửa bản nháp có cấu trúc.
- Nhập hành động tự do.
- Pipeline 5 vai trò AI:
  - Planner.
  - Simulator.
  - Context Validator.
  - Writer.
  - Critic.
- Memory có phân biệt sự thật, quan sát và niềm tin.
- Quan hệ có nhiều chiều và có hướng.
- Save/load, undo hợp lệ, regenerate và branch.
- Streaming văn bản và tiến độ qua SSE.
- Provider:
  - Ollama.
  - Gemini.
  - OpenRouter.
- SQLite cho dữ liệu game và SQLite riêng cho LangGraph checkpoint.
- Web UI bằng Vue 3.
- Chế độ Quality và Fast.
- Công cụ debug dành cho nhà phát triển để xem state, memory, quan hệ và LLM run.

### 3.2. Chưa làm trong MVP

- OpenAI provider trực tiếp.
- PostgreSQL hoặc vector database vận hành thật.
- Multiplayer hoặc collaborative story.
- Microservices.
- Redis, Celery hoặc message broker.
- Fine-tuning model.
- Hệ thống combat RPG đầy đủ.
- Hình ảnh sinh bởi AI, animation, voice/TTS.
- Native mobile app.
- Kubernetes và hạ tầng phân tán.
- Marketplace cho world/character.
- Hỗ trợ hàng chục NPC hoạt động đồng thời.
- Autonomous off-screen simulation cho toàn bộ NPC.
- World tick liên tục, agenda scheduler và rumor propagation toàn thế giới.

### 3.3. Tiêu chí sản phẩm MVP

Một người dùng phải có thể:

1. Tạo một thế giới school romance từ prompt.
2. Xem và sửa dàn nhân vật trước khi bắt đầu.
3. Chơi ít nhất 30 lượt với hành động tự do.
4. Thấy NPC phản ứng khác nhau theo thông tin, tính cách và quan hệ.
5. Thấy một chi tiết cũ được nhắc lại đúng ngữ cảnh.
6. Lưu, tải và rẽ nhánh mà không làm lẫn dữ liệu giữa hai nhánh.
7. Đóng ứng dụng rồi mở lại mà playthrough vẫn nhất quán.

### 3.4. Chính sách nội dung đã duyệt

#### Phân hạng romance và nội dung người lớn

- Tuyến romance có thể bắt đầu với nhân vật từ 14 tuổi.
- Nhân vật 14–15 tuổi chỉ được tham gia romance phù hợp lứa tuổi với người đồng trang lứa:
  - Có thể có rung động, hẹn hò, nắm tay, ôm, hôn nhẹ và xung đột tình cảm.
  - Không có tình dục hóa, khỏa thân tình dục hóa, fetishization hoặc hành vi tình dục.
- Nhân vật 16–17 tuổi có thể có chủ đề tình cảm trưởng thành hơn nhưng vẫn không được mô tả tình dục tường minh:
  - Có thể khai thác ranh giới, đồng thuận, ghen tuông, chia tay và sự thân mật không đồ họa.
  - Nếu câu chuyện chạm tới quan hệ tình dục, chỉ được đề cập gián tiếp/fade-to-black, không eroticize và không mô tả hành vi.
- Không có grooming, bóc lột hoặc quan hệ giữa người trưởng thành và vị thành niên được trình bày như romance tích cực.
- Nội dung tình dục/người lớn tường minh chỉ được phép khi mọi nhân vật tham gia đều từ 18 tuổi tại thời điểm diễn ra scene.
- Nội dung người lớn phải dựa trên sự đồng thuận rõ ràng, có thể rút lại và không bị suy diễn chỉ từ relationship score.
- Timeskip không retroactively hợp thức hóa nội dung khi nhân vật còn dưới 18 tuổi.
- Mỗi World/Playthrough khai báo content rating:
  - teen_14_plus.
  - mature_16_plus.
  - adult_18_plus.
- Player có thể đặt giới hạn chặt hơn world rating; AI không được tự nới giới hạn trong quá trình chơi.

Mốc 16 tuổi không được xem là “tuổi thành niên” trong policy. Nhật Bản quy định tuổi thành niên dân sự là 18 từ ngày 1/4/2022. Việc hình luật Nhật dùng mốc dưới 16 tuổi trong một số quy định về tội phạm tình dục không đồng nghĩa người 16–17 tuổi là người trưởng thành và không phải căn cứ để engine sinh nội dung tình dục tường minh. Product policy giữ ngưỡng 18+ cho nội dung explicit, bất kể bối cảnh truyện đặt tại quốc gia nào.

#### Nội dung nhạy cảm

Cho phép khai thác nội dung nhạy cảm một cách tường minh trong phạm vi rating và consent policy, chẳng hạn tổn thương tâm lý, mất mát, quan hệ phức tạp hoặc chủ đề trưởng thành. World Builder phải:

- Hiển thị content warnings trước khi xác nhận world.
- Cho phép opt-in/opt-out từng nhóm chủ đề.
- Lưu boundary dưới dạng cấu hình có cấu trúc, không chỉ bằng prompt text.
- Không bất ngờ đưa một chủ đề đã bị người chơi loại trừ vào scene.

#### Giới hạn bạo lực

MVP cho phép:

- Xung đột thể chất không đồ họa.
- Đe dọa, nguy hiểm, thương tích và hậu quả ở mức phục vụ câu chuyện.
- Bạo lực có thể gây thất bại hoặc hệ quả lâu dài nếu hợp canon.

MVP không sinh:

- Gore hoặc mô tả thương tích cực đoan kéo dài.
- Tra tấn được mô tả chi li hay nhằm khoái cảm.
- Bạo lực tàn ác/sadistic được fetishize.
- Bạo lực tình dục hoặc hành vi tình dục không đồng thuận được mô tả tường minh.

Những chủ đề bạo lực nhạy cảm chỉ có thể được đề cập không đồ họa khi cần cho bối cảnh, kèm content warning và không biến thành phần thưởng gameplay.

#### Enforcement

ContentPolicy là dữ liệu có cấu trúc và được áp dụng tại nhiều lớp:

1. World Builder validate tuổi, rating, warnings và boundaries.
2. Planner/Simulator nhận policy như constraint bắt buộc.
3. Claim Extractor gắn participants, ages, consent state và content tags.
4. Guard kiểm tra age/rating/consent/violence rules trước khi duyệt SceneSpec:
   - 14–15: teen-safe, không tình dục hóa.
   - 16–17: mature themes nhưng không explicit.
   - 18+: explicit chỉ khi có adult opt-in và consent hợp lệ.
5. Writer chỉ nhận mức mô tả được phép.
6. Critic kiểm tra scene cuối không vượt boundary.

Provider có thể áp dụng giới hạn chặt hơn. Khi provider từ chối, hệ thống báo rõ và có thể chọn hướng kể ít tường minh hơn; không dùng fallback để lách chính sách của provider.

## 4. Nguyên tắc thiết kế bắt buộc

### 4.1. Sự thật và góc nhìn

- Canon là điều thực sự đúng trong thế giới.
- Event là điều thực sự đã xảy ra.
- Observation là điều một nhân vật đã trực tiếp cảm nhận hoặc được kể.
- Belief là điều nhân vật tin, có thể sai.
- Narrative text là cách kể lại, không phải nguồn sự thật độc lập.

### 4.2. Quyền riêng tư thông tin

Context cho mỗi vai trò và nhân vật chỉ chứa dữ liệu họ được phép biết.

- NPC không biết secret nếu chưa quan sát hoặc được tiết lộ.
- Simulator có thể nhận hidden state cần thiết để mô phỏng nhưng Writer chỉ nhận phần được SceneSpec cho phép biểu đạt.
- Player mode không lộ internal beliefs, hidden goals hoặc numeric relationship nếu thiết kế trải nghiệm không cho phép.
- Developer mode mới được inspect toàn bộ.

### 4.3. Tính quyết định ở biên hệ thống

LLM có thể bất định, nhưng các biên phải xác định:

- Schema.
- Validation.
- Quy tắc quyền biết.
- Clamp và hysteresis.
- Ghi lịch sử.
- Idempotency.
- Transaction.
- Branch ancestry.
- Thứ tự thời gian.

### 4.4. Thay đổi nhỏ, có giải thích

Mọi thay đổi quan hệ hoặc tâm lý phải có:

- Giá trị trước.
- Delta được đề xuất.
- Delta sau validation.
- Giá trị sau.
- Sự kiện nguyên nhân.
- Lý do ngắn.
- LLM run và prompt version tạo đề xuất.

### 4.5. Tối ưu sau khi đo

MVP ưu tiên correctness, traceability và khả năng kiểm thử. Chỉ thêm vector DB, cache phân tán hoặc worker riêng khi profiling chỉ ra nhu cầu.

### 4.6. Canonical và derived data

Một artifact được xem là derived nếu có thể xóa và tái dựng 100% từ canonical state/event history. Derived artifact:

- Có version và provenance.
- Có thể stale hoặc temporarily unavailable.
- Không quyết định canon.
- Không được rollback một canonical turn hợp lệ khi job tạo artifact thất bại.

### 4.7. Gameplay quality là invariant sản phẩm

Consistency chưa đủ để tạo trò chơi hay. Engine phải chống narrative degeneracy:

- NPC luôn đồng ý với người chơi.
- Mọi NPC vô thức xoay quanh protagonist.
- Mọi hành động tử tế đều tăng romance.
- NPC liên tục đỏ mặt/rung động không có căn cứ.
- Mục tiêu riêng của NPC biến mất.
- Người chơi không bao giờ thất bại.
- Thread không tiến triển hoặc coincidence luôn cứu người chơi.

Các thuộc tính agency, independence, resistance, pacing và romantic escalation phải được đo bằng scenario eval.

## 5. Kế thừa từ novel-ai-trans

Repository tham chiếu: ../novel-ai-trans

Nguyên tắc kế thừa: lấy hạ tầng và pattern đã chứng minh được, không bê nguyên domain dịch tiểu thuyết sang domain mô phỏng truyện.

### 5.1. Có thể tái sử dụng gần như trực tiếp

- Cấu hình dự án uv.
- Quy tắc Ruff, Pyright và pytest.
- Cấu trúc CLI cho test/build/serve.
- Pattern phân lớp và architecture tests.
- Prompt loader, prompt registry và cache prompt.
- FastAPI app factory.
- Error envelope và exception mapping.
- Vue 3 + Vite + TypeScript + Pinia shell.
- TypeScript API client.
- SSE client.
- Jobs store, settings store và cách đồng bộ trạng thái frontend.
- Logging cơ bản và request correlation.

### 5.2. Tái sử dụng sau khi điều chỉnh đáng kể

- Config snapshot:
  - Giữ nguyên ý tưởng snapshot bất biến theo một job.
  - Mở rộng thành role routing, model capability và game mode.
- LLM base/factory:
  - Giữ interface async, timeout, retry và metadata.
  - Thay contract dịch văn bản bằng structured generation, text generation, streaming và embeddings.
- Provider adapters:
  - Tận dụng cách gọi Ollama, Gemini và OpenRouter.
  - Bỏ logic đặc thù translation.
- Retry/fallback/cancellation:
  - Đổi từ fallback theo tác vụ dịch sang fallback theo role và capability.
- Background jobs:
  - Giữ in-process async runner cho MVP.
  - Thêm khóa một active turn trên mỗi branch.
- Event bus/SSE:
  - Mở rộng event vocabulary cho từng node và token stream.
- LangGraph:
  - Giữ pattern graph builder, node adapter và checkpoint.
  - Viết mới state và node theo turn pipeline.
- Provider settings UI:
  - Chuyển từ một model chung sang cấu hình model cho từng role.

### 5.3. Chỉ kế thừa ý tưởng

- Entity extraction.
- Context analysis.
- Quality checking.
- Relationship inference.
- Cơ chế học từ lịch sử.

Các phần này phải được thiết kế lại vì interactive narrative có event, thời gian, góc nhìn, branch và hidden state.

### 5.4. Không nên kế thừa

- TranslationState.
- Chunking và translation nodes.
- Glossary JSON làm memory chính.
- Relationship chỉ có một nhãn.
- Crawler, EPUB pipeline và file workflow cho dịch truyện.
- Child worker được tối ưu cho tác vụ dịch batch.

### 5.5. Cách thực hiện việc kế thừa

Không copy toàn bộ repository. Với từng module:

1. Viết contract đích trong dự án mới.
2. Chỉ ra phần source có thể dùng.
3. Copy tối thiểu.
4. Đổi namespace và loại bỏ translation assumptions.
5. Viết characterization test nếu hành vi cũ quan trọng.
6. Viết test mới theo domain interactive novel.
7. Ghi nguồn và thay đổi trong docs/reuse-notes.md.

## 6. Tech stack đã chọn

### 6.1. Backend

| Thành phần | Lựa chọn | Vai trò |
|---|---|---|
| Ngôn ngữ | Python 3.14 | Domain, orchestration, API |
| Package manager | uv | Dependency, lockfile, scripts |
| API | FastAPI + Uvicorn | REST, SSE, dependency injection |
| Validation | Pydantic v2 | API DTO và LLM structured output |
| Settings | pydantic-settings | Env và application settings |
| Workflow | LangGraph | Orchestrate turn pipeline |
| Checkpoint | langgraph-checkpoint-sqlite | Resume pipeline, không phải save game |
| ORM | SQLAlchemy 2 async | Persistence abstraction |
| Migration | Alembic | Schema migration |
| Database | SQLite + aiosqlite | Game data trong MVP |
| HTTP client | httpx.AsyncClient | Provider adapters |
| Vector math | NumPy | Exact cosine search ở quy mô MVP |
| Test | pytest, pytest-asyncio | Unit/integration |
| Property test | Hypothesis | Invariant của state/branch |
| HTTP mock | respx | Provider adapter tests |
| Lint/format | Ruff | Chất lượng mã |
| Type check | Pyright | Kiểm tra kiểu |

Nếu Python 3.14 gây xung đột dependency tại thời điểm khởi tạo, hạ xuống phiên bản mới nhất được toàn bộ dependency hỗ trợ và ghi quyết định trong ADR; không tự ý pin một bộ dependency lỗi.

### 6.2. Frontend

| Thành phần | Lựa chọn | Vai trò |
|---|---|---|
| Framework | Vue 3 | UI |
| Ngôn ngữ | TypeScript | Type-safe client |
| Build tool | Vite | Dev/build |
| State | Pinia | Client state |
| Routing | Vue Router | Screens |
| Streaming | Native EventSource hoặc fetch stream wrapper | SSE |
| Unit test | Vitest + Vue Test Utils | Component/store tests |
| E2E | Playwright | Luồng chơi quan trọng |

Không thêm UI framework lớn trong skeleton. Chỉ chọn sau khi có design tokens và màn hình vertical slice.

### 6.3. LLM providers

MVP hỗ trợ:

- Ollama: local generation và optional local embedding.
- Gemini: cloud model trực tiếp.
- OpenRouter: gateway tới các model tương thích.

Không tích hợp OpenAI trực tiếp trong giai đoạn này. Thiết kế interface vẫn trung lập để có thể thêm provider sau mà không đổi domain/application.

Ưu tiên adapter REST async trực tiếp theo pattern từ novel-ai-trans, không ràng buộc toàn bộ hệ thống vào một ChatModel abstraction của LangChain.

### 6.4. Lưu trữ runtime

~~~text
runtime/
├── game.db
├── checkpoints.db
├── logs/
└── exports/

settings.json
~~~

- game.db: dữ liệu sản phẩm có thẩm quyền.
- checkpoints.db: trạng thái thực thi của LangGraph.
- settings.json: lựa chọn model, timeout và UI; secrets không nằm ở đây.
- Secrets: environment variables hoặc secret store của hệ điều hành.

## 7. Kiến trúc tổng thể

~~~text
┌───────────────────────────────────────────────────────┐
│ Vue 3 Web Client                                      │
│ Play UI · World Builder · Saves · Debug Inspector     │
└──────────────────────┬────────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼────────────────────────────────┐
│ FastAPI                                                │
│ Routes · DTO · Auth boundary · Job/SSE coordinator    │
└──────────────────────┬────────────────────────────────┘
                       │ use cases
┌──────────────────────▼────────────────────────────────┐
│ Application Layer                                     │
│ Worlds · Playthroughs · Turns · Branches · Retrieval  │
└──────────────┬──────────────────────┬─────────────────┘
               │                      │
┌──────────────▼───────────────┐  ┌──▼──────────────────┐
│ LangGraph Turn Pipeline      │  │ Domain Engine       │
│ 5 AI editors + support nodes │  │ Rules · Guard · RNG │
└──────────────┬───────────────┘  └──┬──────────────────┘
               │                      │
┌──────────────▼──────────────────────▼─────────────────┐
│ Infrastructure / Services                             │
│ SQLite · Checkpoint · Providers · Embeddings · Logs   │
└───────────────────────────────────────────────────────┘
~~~

### 7.1. Hướng phụ thuộc

~~~text
api → application → domain
graph → application contracts + domain policies
services → implements ports declared inward
domain → không import FastAPI, SQLAlchemy, LangGraph hoặc provider SDK
~~~

### 7.2. Lý do giữ modular monolith

- Một transaction cho toàn bộ turn.
- Dễ debug và chạy local.
- Ít lỗi phân tán.
- Có thể test domain độc lập.
- Vẫn tách module đủ rõ để chuyển worker hoặc database sau này.

MVP không cần microservices.

## 8. Cấu trúc source đích

~~~text
.
├── docs/
│   ├── adr/
│   ├── architecture.md
│   ├── domain-model.md
│   ├── provider-contract.md
│   ├── prompt-contracts.md
│   └── reuse-notes.md
├── migrations/
├── runtime/
├── src/
│   ├── api/
│   │   ├── background/
│   │   ├── routes/
│   │   └── services/
│   ├── application/
│   │   ├── branches/
│   │   ├── playthroughs/
│   │   ├── retrieval/
│   │   ├── turns/
│   │   └── worlds/
│   ├── cli/
│   ├── domain/
│   │   ├── characters.py
│   │   ├── events.py
│   │   ├── knowledge.py
│   │   ├── policies.py
│   │   ├── psychology.py
│   │   ├── relationships.py
│   │   ├── threads.py
│   │   └── worlds.py
│   ├── graph/
│   │   ├── builder.py
│   │   ├── nodes/
│   │   └── state.py
│   ├── models/
│   ├── prompts/
│   ├── services/
│   │   ├── database/
│   │   ├── embeddings/
│   │   ├── llm/
│   │   └── logging/
│   ├── config.py
│   └── paths.py
├── tests/
│   ├── api/
│   ├── application/
│   ├── architecture/
│   ├── domain/
│   ├── graph/
│   └── services/
├── web/
├── pyproject.toml
└── uv.lock
~~~

Đây là cấu trúc đích, không phải yêu cầu tạo sẵn mọi thư mục rỗng. Chỉ tạo package khi có trách nhiệm và test tương ứng.

## 9. Domain model

### 9.1. Aggregate và định danh chính

#### World

Định nghĩa một vũ trụ có thể tái sử dụng:

- Premise.
- Genre và tone.
- Rules/canon.
- Locations.
- Character templates.
- ContentPolicy có rating, topic boundaries, violence ceiling và consent rules.
- Initial narrative seeds.
- World schema version.

World không chứa trạng thái của một lần chơi.

#### Playthrough

Một lần chơi cụ thể:

- Tham chiếu World.
- Player character.
- Root branch.
- Thiết lập provider/config snapshot.
- Clock hiện tại.
- RNG seed.
- Trạng thái active/completed/archived.

#### Branch

Một timeline:

- Parent branch.
- Fork turn.
- Head turn.
- Branch depth.
- Trạng thái active/abandoned.

Mọi query theo nhánh phải tôn trọng ancestry và fork boundary.

#### Turn

Một đơn vị xử lý hành động:

- Input nguyên bản.
- Input chuẩn hóa.
- Base revision.
- Trạng thái queued/running/completed/failed/cancelled.
- Output narrative.
- State patch đã commit.
- Parent turn.
- Config/prompt versions.
- Timing và token usage.

### 9.2. Nhân vật

Tách phần ổn định và phần thay đổi.

#### CharacterProfile

- Identity và aliases.
- Tuổi, vai trò, background.
- Ngoại hình và cách nói.
- Traits tương đối ổn định.
- Values.
- Boundaries.
- Long-term goals.
- Likes/dislikes.
- Secrets ban đầu.

#### CharacterState

- Vị trí hiện tại.
- Physical condition.
- Emotional state.
- Short-term goals.
- Attention target.
- Stress/fatigue.
- Inventory reference.
- Last active turn.
- Phiên bản state.

Không sửa CharacterProfile để biểu diễn cảm xúc tạm thời.

### 9.3. Event

Event là log sự thật bất biến sau commit:

- Loại sự kiện.
- Thời điểm trong truyện.
- Location.
- Actors, targets và witnesses.
- Payload có cấu trúc.
- Salience.
- Emotional intensity.
- Causation references.
- Turn và branch.

Correction không sửa im lặng event cũ; tạo event hiệu chỉnh hoặc migration có audit.

### 9.4. KnowledgeClaim và CanonFact

KnowledgeClaim là biểu diễn máy đọc được của một proposition. Cấu trúc tối thiểu:

- claim_id.
- claim_type.
- subject_id.
- predicate.
- object_id hoặc typed_value.
- polarity.
- qualifiers có schema, ví dụ location, manner hoặc context.
- valid_time range.
- branch scope.
- schema_version.
- normalized fingerprint.
- provenance.

Ví dụ:

~~~text
subject_id = yuki
predicate  = romantic_interest
object_id  = akira
polarity   = positive
~~~

CanonFact không phải một câu text khác. Nó là một assertion có thẩm quyền lên KnowledgeClaim:

- fact_id.
- claim_id.
- status: active, retracted hoặc superseded.
- source event/rule.
- asserted turn/time.
- superseded_by.

Claim links biểu diễn quan hệ:

- supports.
- contradicts.
- derived_from.
- refines.
- supersedes.

MVP phải có predicate registry hữu hạn cho các mutation quan trọng. Một claim type không được schema biết tới không thể trở thành authoritative mutation; nó chỉ có thể ở lại dưới dạng non-canonical prose hoặc phải qua schema evolution.

### 9.5. Observation

Mỗi nhân vật có observation riêng:

- Observer.
- Event hoặc nguồn thông tin.
- Observed claim.
- Cách quan sát: thấy, nghe, được kể hoặc suy ra.
- Confidence.
- Distortion.
- Timestamp.
- Claim links tới proposition được observation hỗ trợ hoặc phản bác.

Ví dụ “Alice thấy Yuki đỏ mặt” là một observed claim. Nó có thể hỗ trợ nhưng không đồng nhất với claim “Yuki thích Akira”.

Không dùng một memory chung kèm danh sách known_by vì các nhân vật có thể thấy cùng sự kiện theo cách khác nhau.

### 9.6. Belief

- Believer.
- Claim được tin.
- Stance: supports, rejects hoặc uncertain.
- Confidence.
- Evidence và counter-evidence qua claim links.
- Source reliability.
- Created/updated turn.

Belief có thể sai, mâu thuẫn hoặc chưa xác định. Truth được xác định bằng quan hệ với CanonFact nếu engine có fact tương ứng; belief không tự mang quyền tạo sự thật.

Chuỗi hợp lệ có thể là:

~~~text
CanonFact: Yuki thực sự thích Akira

Observation của Alice:
Alice thấy Yuki đỏ mặt khi Akira tới gần

Belief của Alice:
Alice tin Yuki có thể thích Akira, confidence = 0.72
~~~

Ba record có liên hệ nhưng không bị đồng nhất thành một fact.

### 9.7. Knowledge authorization

Để một nhân vật hành động dựa trên claim:

1. Claim phải được chuẩn hóa.
2. Query phải dùng đúng playthrough, branch ancestry và time boundary.
3. Nhân vật phải có observation/belief/evidence phù hợp hoặc claim phải là public knowledge.
4. Confidence phải đạt policy của hành động nếu cần.
5. Mọi source link phải tồn tại.

Context Validator có thể đánh giá sự tương đồng/mâu thuẫn giàu ngữ nghĩa. Guard kiểm tra deterministic trên claim ID/type, owner, scope, time và evidence links.

### 9.8. NarrativeThread và NarrativeHook

Memory trả lời “điều gì đã xảy ra/được biết”. Thread trả lời “điều gì đang tiến triển”.

NarrativeThread:

- Premise.
- Participants.
- Status: seeded, active, escalating, resolved, abandoned.
- Stakes.
- Progress.
- Urgency.
- Last advanced turn.
- Resolution conditions.

NarrativeHook:

- Setup.
- Expected payoff window.
- Related memory/event.
- Visibility.
- Status.

Không dùng memory retrieval thay cho quản lý nhịp truyện.

### 9.9. Tiến triển ngoài camera trong MVP

MVP không tick mọi NPC sau mỗi turn. Off-screen change chỉ được tạo khi có một trong các trigger:

- ScheduledEvent đã tồn tại.
- NarrativeThread có mốc tiến triển đến hạn.
- Planner materialize một diễn biến cần thiết cho scene hiện tại và Guard xác nhận causal chain.

Off-screen event phải có actors, world time, location, causes và visibility như event bình thường. Không được retroactively tạo một sự kiện mâu thuẫn với observation/canon đã có.

Hậu MVP mới cân nhắc:

- WorldScheduler.
- NPCAgenda.
- WorldTick.
- Goal planning ngoài camera.
- Rumor propagation chủ động.

## 10. Hệ thống quan hệ và tâm lý

### 10.1. Quan hệ có hướng

Quan hệ A → B khác B → A. Mỗi directed edge có các chiều:

| Chỉ số | Ý nghĩa | Nguồn cập nhật chính |
|---|---|---|
| affection | Sự yêu mến | Simulator đề xuất, policy giới hạn |
| attraction | Sức hấp dẫn lãng mạn/thể chất | Simulator đề xuất, policy giới hạn |
| trust | Tin cậy | Simulator đề xuất từ event có bằng chứng |
| respect | Tôn trọng | Simulator đề xuất từ appraisal |
| comfort | Cảm giác an toàn/tự nhiên | Simulator đề xuất + context |
| fear | Sợ hãi | Simulator đề xuất + decay policy |
| resentment | Oán giận | Simulator đề xuất + decay policy |
| familiarity | Mức quen thuộc | Engine suy ra từ shared exposure |

Dependency không nằm trong core vector MVP vì một scalar dễ trộn emotional reliance, practical reliance, attachment và codependence. Nếu gameplay cần, ADR riêng phải tách và định nghĩa rõ các dimension trước khi thêm.

Mỗi dimension có semantic domain rõ ràng: signed appraisal có thể dùng -1 đến 1; intensity/accumulation có thể dùng 0 đến 1. API/debug có thể map sang -100…100 hoặc 0…100. Domain và conversion phải được chốt trong ADR trước khi code.

### 10.2. Update policy theo từng dimension

Không dùng chung công thức new = old + delta cho mọi metric.

| Chỉ số | Policy ban đầu |
|---|---|
| affection | Tăng/giảm chậm; hành động tử tế bình thường không mặc định tăng |
| attraction | Có thể biến động nhanh hơn nhưng cần trigger phù hợp và không đồng nghĩa affection |
| trust | Tăng chậm; có thể giảm mạnh khi phản bội; phục hồi cần evidence |
| respect | Nhạy với hành động thể hiện năng lực, giá trị hoặc vi phạm nguyên tắc |
| comfort | Phụ thuộc context, safety và familiarity |
| fear | Context-dependent; có decay nếu không còn threat |
| resentment | Có decay chậm; được củng cố bởi repeated grievance |
| familiarity | Gần monotonic; engine tính từ shared scenes, conversations, meaningful events và elapsed relationship duration |

Mỗi policy định nghĩa:

- Evidence/event types hợp lệ.
- Max delta mỗi lượt.
- Gain/loss asymmetry.
- Decay.
- Saturation/diminishing return.
- Trait modifiers.
- Hysteresis nếu có.

### 10.3. Quy trình cập nhật quan hệ

1. Simulator chỉ đề xuất delta cho appraisal metrics.
2. Engine kiểm tra actor/target tồn tại.
3. Policy kiểm tra action/event có đủ căn cứ.
4. Clamp theo giới hạn mỗi lượt và trait sensitivity.
5. Áp dụng diminishing return.
6. Áp dụng hysteresis để nhãn không nhảy liên tục.
7. Engine tự tính familiarity và các derived metrics.
8. Ghi RelationshipChange với provenance.
9. Tính lại derived labels nếu cần.

LLM không ghi trực tiếp con số cuối cùng.

### 10.4. Derived labels

Các nhãn như stranger, acquaintance, friend, close_friend, crush, lover, rival hoặc hostile là kết quả suy ra từ vector quan hệ, lịch sử và context; chúng không thay thế vector.

Ví dụ, crush có thể cần attraction đủ cao, affection dương và familiarity tối thiểu. Lover cần thêm mutual commitment event thay vì chỉ đạt threshold.

### 10.5. Ghen tuông và quan hệ chồng chéo

Jealousy không phải một scalar cố định trên A → B. Nó là tension ba ngôi:

- Observer: người có cảm xúc.
- Rival: người được xem là đối thủ.
- Focus: người/điều được tranh giành.
- Trigger event.
- Intensity.
- Appraisal.
- Decay.
- Visibility.

Lưu trong emotional_tensions để mô hình hóa triangle, rivalry và hiểu nhầm.

### 10.6. Trạng thái tâm lý

PsychologicalState tối thiểu:

- Valence.
- Arousal.
- Dominance/control.
- Stress.
- Fatigue.
- Current needs.
- Active goals.
- Appraisals.
- Suppressed emotions.

Simulator nhận:

- Traits và values.
- Psychological state trước lượt.
- Beliefs được phép dùng.
- Quan hệ có liên quan.
- Event/intent hiện tại.
- Social context.

Simulator trả:

- Phản ứng bên trong.
- Hành động/lời thoại đề xuất.
- Goal changes.
- State deltas.
- Relationship delta proposals.
- Observation/belief proposals.
- Uncertainty.

## 11. Hệ thống memory

### 11.1. Các lớp memory

| Lớp | Nội dung | Có thẩm quyền |
|---|---|---|
| Canon | Luật và CanonFact trên typed claims | Có |
| Current state | Trạng thái hiện tại | Có |
| Event memory | Việc đã xảy ra | Có |
| Observation | Điều một nhân vật tiếp nhận | Theo góc nhìn |
| Belief | Điều một nhân vật tin | Có thể sai |
| Relationship history | Cách quan hệ thay đổi | Có |
| Narrative summary | Bản nén để prompt | Không |
| Player preference | Sở thích trải nghiệm | Có trong phạm vi profile |
| Retrieval index | Chỉ mục tìm kiếm | Không, có thể tái tạo |

### 11.2. Canonical memory write path

Canonical Record Builder không đọc văn xuôi rồi tự phát minh canon. Nó nhận:

- Typed StatePatch đã được Guard duyệt.
- Event records.
- CanonFact/KnowledgeClaim assertions.
- Observations và beliefs được Simulator đề xuất.
- Relationship changes.
- Thread changes.

Nó chuẩn hóa các authoritative records để đưa vào canonical transaction. Narrative text chỉ được gắn vào turn; không được reverse-extract thành sự thật.

Sau commit, Derived Job Enqueuer xử lý:

- Summary.
- Embedding.
- Retrieval/FTS index phụ trợ.
- Consolidation.
- Analytics.

Derived job có retry và idempotency riêng. Lỗi derived job không rollback turn; context của lượt kế tiếp fallback về current state và raw/recent events.

### 11.3. Retrieval pipeline

Thứ tự bắt buộc:

1. Xác định scope:
   - Playthrough.
   - Branch ancestry.
   - Turn/time boundary.
   - Owner/observer.
   - Entity.
2. Hard filter trong SQL.
3. Candidate retrieval bằng keyword/entity/thread.
4. Optional vector similarity.
5. Re-rank.
6. Deduplicate.
7. Budget theo token và vai trò.
8. Ghi retrieval trace.

Tuyệt đối không vector-search toàn bộ rồi mới lọc quyền biết, vì có thể rò memory từ nhánh khác hoặc nhân vật khác.

Retrieval có hai pha:

- Initial retrieval: lấy context đủ để Planner và Simulator làm việc.
- Targeted consistency retrieval: sau khi đã biết các claim/mutation được đề xuất, truy vấn chính xác evidence cần để validate chúng.

Validator không được giả định initial context là toàn bộ sự thật.

### 11.4. Công thức xếp hạng ban đầu

Một điểm khởi đầu có thể là:

~~~text
score =
  w_semantic  × semantic_similarity
+ w_recency   × recency
+ w_salience  × salience
+ w_emotion   × emotional_intensity
+ w_entity    × entity_overlap
+ w_goal      × active_goal_relevance
+ w_thread    × narrative_thread_relevance
+ w_payoff    × setup_payoff_relevance
~~~

Mọi feature được chuẩn hóa. Weight phải nằm trong config versioned và được tune bằng scenario eval, không hardcode rải rác.

### 11.5. Vector search trong SQLite MVP

Không cần vector database ngay.

Thiết kế MVP:

- Dùng SQL hard filters để lấy candidate nhỏ.
- Optional tạo embedding qua Ollama.
- Lưu vector dạng BLOB cùng:
  - model.
  - dimensions.
  - embedding version.
  - content hash.
  - created timestamp.
- Dùng NumPy exact cosine trên candidate set.

Embeddings là derived data:

- Có thể xóa và rebuild.
- Không nằm trong transaction logic quyết định canon.
- Phải invalid khi model/dimension/content hash đổi.

Nếu embeddings chưa bật, hệ thống vẫn hoạt động với entity, FTS/keyword, salience, recency và thread relevance.

### 11.6. Consolidation

Sau khi MVP ổn định:

- Gom các event nhỏ thành episodic summary.
- Giữ raw events.
- Tạo candidate durable-fact projections có provenance.
- Phát hiện belief conflict.
- Giảm trọng số memory không còn liên quan.
- Không mất setup chưa payoff.

Consolidation phải idempotent và có version. Candidate projection không tự assert CanonFact; muốn trở thành authoritative vẫn phải đi qua typed claim policy và Guard.

## 12. Pipeline một lượt chơi

### 12.1. Luồng đầy đủ

~~~text
Player Action
    ↓
Input Normalizer
    ↓
Initial Context Builder / Retriever
    ↓
Planner AI
    ↓
Simulator AI
    ↓
Claim Extractor
    ↓
Targeted Consistency Retrieval
    ↓
Context Validator AI
    ↓
Deterministic State Guard
    ↓
Writer AI
    ↓
Critic AI
    ↓
Canonical Record Builder
    ↓
Canonical Atomic Commit
    ↓
Derived Job Enqueuer
    ↓
SSE completed
~~~

Năm “biên tập viên” AI vẫn là Planner, Simulator, Context Validator, Writer và Critic. Input Normalizer, Initial Context Builder, Claim Extractor, Targeted Consistency Retriever, State Guard, Canonical Record Builder, Commit và Derived Job Enqueuer là support/deterministic nodes. Một support node chỉ được gọi thêm model nếu contract thực sự cần; việc đó không biến nó thành nguồn authority.

### 12.2. Input Normalizer

- Giữ nguyên raw input.
- Phân loại action, dialogue, meta-command.
- Chuẩn hóa entity references.
- Phát hiện prompt injection/meta request.
- Không tự quyết định outcome.

### 12.3. Initial Context Builder

Đây là assembler deterministic trước Planner:

- Load snapshot/head revision.
- Load current location và active characters.
- Load relevant profiles/state.
- Retrieve observations/beliefs đúng quyền.
- Retrieve relationship edges.
- Retrieve active threads/hooks.
- Chọn recent transcript.
- Áp token budget theo role.
- Tạo context manifest có ID và version.

Initial context được tối ưu cho planning/simulation, không cố nhồi mọi canon và lịch sử vào prompt.

### 12.4. Planner AI

Planner điều hướng câu chuyện, nhưng không viết chương hoàn chỉnh.

Đầu ra TurnPlan:

- Interpreted player intent.
- Candidate beats.
- Intended focus.
- Active threads được advance hoặc defer.
- Characters involved.
- Stakes.
- Required checks.
- Possible outcomes.
- Pacing note.
- Safety constraints.

### 12.5. Simulator AI

Simulator giả lập phản ứng:

- Đánh giá từng NPC độc lập từ profile, state, belief và quan hệ của họ.
- Đề xuất outcome.
- Đề xuất event/state/relationship/belief deltas.
- Nêu uncertainty.
- Không viết văn xuôi cuối.

Đầu ra SimulationResult có cấu trúc. Mọi mutation phải dùng typed claim/state operation hoặc sẽ bị từ chối trước Guard.

### 12.6. Claim Extractor và Targeted Consistency Retrieval

Claim Extractor duyệt TurnPlan và SimulationResult để tạo:

- ProposedClaims.
- ProposedStateMutations.
- KnowledgeRequirements theo từng actor.
- ValidationQueries.
- Claim-to-mutation mapping.

Nếu SimulationResult đã tuân schema typed, phần lớn extraction là deterministic. Một structured model call nhỏ chỉ là fallback cho nội dung chưa phân loại và output của nó vẫn phải qua schema validation.

Targeted Consistency Retriever truy vấn riêng cho từng validation query:

- Actor có thể ở location đó không?
- Actor có observation/belief nào về claim này tại thời điểm đó?
- Claim nào support hoặc contradict mutation?
- CanonFact nào có cùng subject/predicate/time scope?
- Thread/hook nào sẽ bị mâu thuẫn hoặc bỏ quên?

Mọi query vẫn hard-filter playthrough, branch ancestry, time và owner trước semantic ranking. Đầu ra là TargetedEvidenceManifest có IDs, scopes và scores.

### 12.7. Context Validator AI

Đây là “Context editor” sau Simulator và targeted retrieval:

- So kết quả với initial context lẫn TargetedEvidenceManifest.
- Phát hiện nhân vật biết điều họ chưa thể biết.
- Phát hiện tính cách, timeline hoặc location không nhất quán.
- Phát hiện bỏ quên setup/payoff quan trọng.
- Phát hiện proposed claim bị evidence phản bác.
- Đề xuất sửa plan/simulation.

Đầu ra ConsistencyReport:

- violations.
- severity.
- evidence references.
- recommended corrections.
- pass/fail recommendation.

AI validator chỉ tư vấn; State Guard mới là cửa quyết định deterministic.

Nếu evidence còn thiếu, Validator phải trả insufficient_evidence thay vì PASS mặc định.

### 12.8. Deterministic State Guard

Guard kiểm tra:

- Base revision còn là head.
- ID và references hợp lệ.
- Branch/time scope.
- Canon constraints.
- Actor có mặt và có khả năng hành động.
- Delta nằm trong range.
- Mọi fact/state mutation có typed claim/operation hợp lệ.
- KnowledgeRequirement được authorize bằng public claim hoặc observation/belief đúng owner/scope/time.
- Claim/evidence links tồn tại và không vượt branch boundary.
- Không có state transition bất hợp lệ.
- Không trùng idempotency key.
- SceneSpec không chứa fact chưa được phê chuẩn.
- Content rating phù hợp tuổi của mọi participant.
- Consent requirements thỏa mãn với adult scene.
- Content/violence tags không vượt ContentPolicy của world và player.

Khi fail:

- Cho Planner/Simulator sửa trong số vòng giới hạn.
- Hoặc fail turn với lỗi có thể giải thích.
- Không commit một phần.

Guard không cố hiểu prose tự do. Bất kỳ phần nào không biểu diễn được bằng domain claim/operation đều không có quyền trở thành authoritative.

### 12.9. Writer AI

Writer nhận SceneSpec đã duyệt, không nhận toàn bộ database.

SceneSpec gồm:

- Approved beats.
- Visible actions.
- Allowed dialogue intents.
- POV.
- Tone/style.
- Required continuity details.
- Facts được phép tiết lộ.
- Facts bị cấm tiết lộ.
- Length target.

Writer trả:

- Narrative text.
- Optional paragraph/beat mapping.
- Không trả state patch.

### 12.10. Critic AI

Critic kiểm tra:

- Văn phong.
- Nhịp.
- Lặp từ.
- POV.
- Show-versus-tell.
- Dialogue voice.
- Chi tiết bắt buộc.
- Chi tiết bị cấm.
- Sự khớp với SceneSpec.

Critic trả CritiqueResult và, nếu cần, revision instructions. Số vòng Writer ↔ Critic phải giới hạn, mặc định một lần sửa.

Critic không được thay outcome hoặc state.

### 12.11. Canonical Record Builder và Commit

Canonical Record Builder tạo authoritative records từ approved patch. Commit service ghi final narrative, events, claims/facts, observations, beliefs, state, relationships, threads và branch head trong một transaction.

Chỉ sau commit thành công mới phát completed và cập nhật branch head.

### 12.12. Derived jobs

Canonical transaction chỉ ghi một outbox/task intent tối thiểu nếu cần. Sau commit:

~~~text
Canonical turn committed
    ↓
Derived jobs
├── summary
├── embedding
├── retrieval index
├── consolidation
└── analytics
~~~

Mỗi job có idempotency key, status, retry policy và artifact version. Nếu summarizer OOM hoặc embedding provider lỗi, turn vẫn hoàn tất và lượt sau dùng raw/recent data.

### 12.13. Quality mode, Fast mode và physical calls

Quality:

- Thực hiện đầy đủ contract của năm logical AI roles.
- Có một vòng repair nếu Context Validator/Guard yêu cầu.
- Có một vòng Writer revision từ Critic.
- Có thể dùng năm model calls riêng nếu cấu hình ưu tiên chất lượng.

Fast:

- Planner + Simulator có thể fuse trong một call với hai output section được validate riêng.
- Context Validator chỉ chạy khi risk score cao hoặc luôn dùng model nhỏ.
- Writer + Critic có thể fuse nếu benchmark chứng minh chất lượng; Critic contract vẫn có artifact riêng.
- Critic có thể dùng local model hoặc deterministic checklist ở scene rủi ro thấp.
- Các node, role artifact và trace vẫn giữ nguyên.

Không bỏ Guard trong bất kỳ mode nào.

Execution planner phải ghi rõ:

- Logical role.
- Physical call ID.
- Provider/model.
- Fused roles.
- Skip/conditional reason.
- Output contract và validator.

### 12.14. LangGraph state

TurnGraphState chỉ giữ dữ liệu cần cho một run:

- turn_run_id.
- playthrough_id.
- branch_id.
- base_revision.
- raw/normalized input.
- context manifest.
- plan.
- simulation.
- proposed claims.
- knowledge requirements.
- validation queries.
- targeted evidence manifest.
- consistency report.
- approved patch.
- scene spec.
- draft.
- critique.
- final narrative.
- derived job intents.
- retry counters.
- errors.
- config snapshot ID.

Không nhét toàn bộ lịch sử hoặc ORM session vào graph state.

Thread ID của checkpoint dùng turn_run_id, không dùng playthrough_id, để các turn không ghi đè checkpoint của nhau.

## 13. LLM provider architecture

### 13.1. Các role

- world_builder.
- planner.
- simulator.
- context_validator.
- writer.
- critic.
- memory.
- embedding.

### 13.2. Provider port

Provider interface cần các năng lực:

~~~text
generate_structured(request, schema) → StructuredResponse
generate_text(request) → TextResponse
stream_text(request) → AsyncIterator[TextChunk]
embed(texts) → EmbeddingResponse
close()
~~~

Không phải provider nào cũng hỗ trợ tất cả. Capability matrix quyết định routing.

### 13.3. Metadata bắt buộc

Mỗi response lưu:

- provider.
- model.
- role.
- request ID.
- latency.
- token usage nếu có.
- finish reason.
- retries.
- fallback chain.
- schema/prompt version.
- config snapshot.

### 13.4. Role routing

Ví dụ cấu hình ban đầu:

| Role | Ưu tiên | Fallback |
|---|---|---|
| world_builder | Gemini/OpenRouter | Ollama |
| planner | Gemini/OpenRouter | Ollama |
| simulator | Gemini/OpenRouter | Ollama |
| context_validator | Ollama model nhỏ | Gemini/OpenRouter |
| writer | Model văn phong tốt | Ollama |
| critic | Ollama model nhỏ | Gemini/OpenRouter |
| memory | Ollama model nhỏ | Rule-based |
| embedding | Ollama embedding | Không dùng vector |

Đây chỉ là default; người dùng có thể đổi trong settings theo capability.

### 13.5. Execution plan: role → physical call

Trước khi chạy graph, ExecutionPlanner tạo PhysicalCallPlan dựa trên mode, capability, latency budget và config:

~~~text
Quality example
Call 1 → Planner
Call 2 → Simulator
Call 3 → Context Validator
Call 4 → Writer
Call 5 → Critic

Fast example
Call 1 → Planner + Simulator
Call 2 → Context Validator, conditional/local
Call 3 → Writer + Critic contract
~~~

Một fused call phải trả các artifact tách biệt theo schema. Metrics và eval được gắn cho từng logical role lẫn physical call để có thể benchmark việc fuse/split.

### 13.6. Structured output

Quy trình:

1. Chọn schema version.
2. Adapter dùng native JSON/schema mode nếu provider hỗ trợ.
3. Parse bằng Pydantic.
4. Chạy semantic validator.
5. Nếu lỗi, repair một số lần giới hạn.
6. Nếu vẫn lỗi, fallback hoặc fail rõ ràng.

Không parse JSON bằng regex.

### 13.7. Timeout, retry và fallback

- Timeout riêng theo role.
- Retry chỉ cho lỗi transient.
- Exponential backoff có jitter.
- Tôn trọng cancellation.
- Không retry mù sau khi không rõ provider đã hoàn tất request hay chưa.
- Ghi từng attempt.
- Fallback không được làm thay đổi schema contract.

### 13.8. Prompt management

Mỗi prompt có:

- role.
- semantic version.
- input contract.
- output schema version.
- template hash.
- test fixtures.
- changelog.

Prompt được load qua registry/cache kế thừa từ novel-ai-trans. Prompt text không rải trong node code.

## 14. Persistence với SQLite

### 14.1. Cấu hình SQLite

Khi mở connection:

- PRAGMA foreign_keys = ON.
- Journal mode WAL.
- busy_timeout hợp lý.
- Transaction boundary ở application service.
- Một writer path có kiểm soát cho turn commit.

Không xem WAL là giải pháp cho mọi dạng concurrency. Quy tắc sản phẩm vẫn là một active turn trên mỗi branch.

### 14.2. Các nhóm bảng

#### World và playthrough

- worlds.
- playthroughs.
- branches.
- turns.
- snapshots.

#### Entity và state

- entities.
- characters.
- character_states.
- locations.
- items.
- inventories.

#### Event và knowledge

- events.
- event_participants.
- knowledge_claims.
- canon_facts.
- claim_links.
- observations.
- beliefs.
- belief_evidence.

#### Quan hệ và narrative

- relationships.
- relationship_changes.
- emotional_tensions.
- narrative_threads.
- narrative_hooks.

#### Derived và observability

- narrative_summaries.
- memory_embeddings.
- derived_jobs.
- outbox_events.
- llm_runs.
- prompt_versions.
- retrieval_traces.
- jobs.

### 14.3. Quy ước schema

- Application ID dùng UUID lưu dạng TEXT để tương thích SQLite/PostgreSQL.
- Timestamp lưu UTC và chuyển timezone ở UI.
- Không phụ thuộc SQLite native enum; dùng text + constraint/validation.
- Cột thường xuyên filter/join phải là cột thật.
- JSON chỉ dùng cho payload thưa, có version, không thay mọi cấu trúc quan trọng.
- Foreign key rõ ràng.
- Unique/index cho idempotency, ancestry queries, owner/time và current state.
- Mọi migration qua Alembic.
- Với SQLite schema change phức tạp, dùng Alembic batch operations.

### 14.4. Snapshot và event log

Mô hình hybrid:

- Events/change logs là lịch sử có thẩm quyền.
- Current-state tables giúp đọc nhanh.
- Snapshot định kỳ giúp load/replay nhanh. Vì có thể tái dựng từ event history và current state, snapshot là acceleration artifact, không phải điều kiện để canonical turn commit thành công.

Snapshot chứa:

- Playthrough/branch revision.
- Current entities/states.
- Relationship vectors.
- Active beliefs/threads.
- Clock/RNG state.
- Schema version.
- Hash/checksum.

Snapshot không xóa event history. Snapshot được tạo sau canonical commit bằng derived job và có checksum/version.

### 14.5. Vòng đời commit một lượt

1. Mở transaction.
2. Kiểm tra branch head bằng optimistic concurrency.
3. Insert/update turn ở trạng thái committing.
4. Ghi events và participants.
5. Ghi typed knowledge claims, CanonFact assertions và claim links.
6. Ghi observations/beliefs/evidence.
7. Ghi state changes.
8. Ghi relationship/tension changes.
9. Ghi thread/hook changes.
10. Ghi final narrative.
11. Ghi outbox/derived-job intents tối thiểu.
12. Cập nhật branch head và revision.
13. Mark turn completed.
14. Commit.
15. Phát SSE completed sau commit.
16. Derived workers tạo summary, snapshot, index, embeddings, consolidation và analytics.

Bất kỳ lỗi nào trước bước commit đều rollback.

Lỗi ở bước 16 chỉ đánh dấu/retry derived job, không thay trạng thái completed của turn. Reconciler có thể quét completed turns thiếu artifact để phục hồi ngay cả khi outbox dispatch bị gián đoạn.

### 14.6. Canonical và derived consistency

Canonical read path không phụ thuộc vào derived artifacts.

Khi summary/index/snapshot:

- Chưa có: fallback raw/recent events và current tables.
- Stale: bỏ qua nếu source revision/hash không khớp.
- Lỗi: enqueue retry có backoff.
- Đổi schema/model: invalidate và rebuild.

Derived artifact luôn lưu source revision, builder version và content hash.

### 14.7. Undo, regenerate và branch

- Undo trên một branch chưa có descendant có thể di chuyển head về ancestor theo policy.
- Regenerate không ghi đè lịch sử đã công bố; mặc định tạo branch mới từ parent turn.
- Fork ghi parent_branch_id và fork_turn_id.
- Query branch phải lấy ancestor events đến đúng fork point, sau đó events của branch con.
- UI hiển thị rõ đang ở branch nào.

## 15. Khả năng mở rộng PostgreSQL và vector database

SQLite cho MVP là lựa chọn ổn, miễn là ranh giới persistence được giữ sạch.

### 15.1. Chuẩn bị từ đầu

- Repository ports ở application/domain boundary.
- SQLAlchemy thay vì SQL SQLite viết rải rác.
- UUID TEXT, UTC, portable types.
- Alembic là nguồn migration duy nhất.
- Không dùng rowid làm domain ID.
- Không dựa vào behavior lỏng của SQLite về kiểu dữ liệu.
- Transaction tests chạy trên repository contract.
- Embedding index là adapter riêng.

### 15.2. Khi nào chuyển PostgreSQL

Chỉ chuyển khi có một hoặc nhiều dấu hiệu:

- Nhiều process/server cùng ghi.
- Nhiều người dùng đồng thời.
- Lock contention đáng kể.
- Cần backup/replication/operations tốt hơn.
- Query analytics và indexing phức tạp.
- Cần row-level locking hoặc job leasing đáng tin cậy.

### 15.3. Lộ trình chuyển

1. Dựng PostgreSQL schema từ Alembic.
2. Chạy repository contract test trên cả SQLite và PostgreSQL.
3. Viết migration/export tool có checksum.
4. Copy dữ liệu theo dependency order.
5. So sánh counts, hashes và replay fixtures.
6. Chạy read-only shadow validation.
7. Cut over sau backup.

### 15.4. Vector database

Hai hướng hợp lý:

- PostgreSQL + pgvector: mặc định nên chọn đầu tiên khi quy mô vừa, vận hành đơn giản.
- Dedicated vector database: chỉ khi quy mô, latency, filtering hoặc multi-tenant workload thực sự đòi hỏi.

PostgreSQL vẫn là nguồn sự thật. Vector store chỉ chứa:

- memory ID.
- embedding.
- scope metadata tối thiểu.
- model/version/hash.

Đồng bộ bằng outbox hoặc derived-data jobs có retry. Mọi vector index phải rebuild được từ dữ liệu gốc.

## 16. Application use cases

Các use case chính:

- CreateWorld.
- GenerateWorldDraft.
- ValidateWorldDraft.
- ConfirmWorld.
- CreatePlaythrough.
- GetPlaythrough.
- SubmitTurn.
- CancelTurn.
- RegenerateTurn.
- ForkBranch.
- SwitchBranch.
- ListCharacters.
- GetCharacterPublicProfile.
- InspectCharacterMemory.
- InspectRelationships.
- InspectTimeline.
- UpdateProviderSettings.
- TestProviderConnection.
- ExportPlaythrough.

Mỗi use case:

- Nhận command/query DTO.
- Kiểm tra authorization và invariant.
- Gọi domain/repository/provider qua port.
- Sở hữu transaction boundary khi có write.
- Không trả ORM model trực tiếp ra API.

## 17. API, jobs và streaming

### 17.1. REST resources

Nhóm route dự kiến:

~~~text
/api/worlds
/api/playthroughs
/api/branches
/api/turns
/api/characters
/api/relationships
/api/jobs
/api/providers
/api/settings
/api/debug
~~~

API response dùng error envelope thống nhất từ pattern của novel-ai-trans.

### 17.2. Background turn job

MVP dùng in-process async runner:

- SubmitTurn tạo turn/job và trả ID ngay.
- Runner chạy LangGraph.
- SSE stream tiến độ và token.
- App restart đánh dấu job đang chạy là interrupted.
- Người dùng có thể retry/resume theo policy.

Quy tắc concurrency:

- Chỉ một active turn trên một branch.
- Các branch khác nhau có thể chạy song song trong giới hạn global semaphore.
- Nếu base revision không còn là head khi commit, turn bị stale và không commit.
- Idempotency key ngăn submit lặp do retry từ client.

### 17.3. Cancellation

- Cancellation token đi qua graph và provider adapter.
- Kiểm tra cancellation giữa các node và trong stream.
- Cancel trước commit: rollback/không ghi domain state.
- Cancel khi commit đã hoàn tất: turn vẫn completed; UI không được hiển thị cancelled giả.
- Không thể hứa hủy request bên trong provider nếu provider không hỗ trợ, nhưng phải bỏ kết quả đúng cách.

### 17.4. SSE events

Event vocabulary:

- job_queued.
- context_started.
- context_completed.
- planner_started.
- planner_completed.
- simulator_started.
- simulator_completed.
- validator_started.
- claims_extracted.
- targeted_retrieval_started.
- targeted_retrieval_completed.
- validator_completed.
- guard_rejected.
- repair_started.
- writer_started.
- writer_token.
- writer_completed.
- critic_started.
- critic_completed.
- retrying.
- committing.
- derived_jobs_queued.
- completed.
- failed.
- cancelled.

Mỗi event có:

- event ID tăng dần trong job.
- job/turn ID.
- timestamp.
- phase.
- payload version.
- safe user-facing payload.

Client reconnect gửi Last-Event-ID; server replay phần event buffer còn lưu.

### 17.5. API security tối thiểu

Local-first không có nghĩa là bỏ security:

- Bind localhost theo mặc định.
- CORS allowlist.
- Không trả API key về client sau khi lưu.
- Redact secrets khỏi logs/error.
- Giới hạn độ dài user input.
- Tách player endpoints và debug endpoints.
- Debug mode tắt mặc định trong bản đóng gói.
- Không cho nội dung người dùng thay đổi system prompt hoặc tool policy.

## 18. Frontend

### 18.1. Các màn hình

- Home / Library.
- New World.
- World Draft Review.
- New Playthrough.
- Play Screen.
- Save/Branch Timeline.
- Characters.
- Settings / Providers.
- Developer Inspector.

### 18.2. Play Screen

Thành phần chính:

- Narrative transcript.
- Tên người nói và dialogue.
- Input hành động tự do.
- Nút gửi/hủy.
- Progress theo pipeline.
- Character presence panel.
- Scene/location/time header.
- Save/branch controls.
- Retry/regenerate khi lỗi.

Không stream Writer text như canon cuối cùng trước khi Critic hoàn tất mà không báo rõ. Hai lựa chọn:

- Stream dưới nhãn draft rồi replace bằng bản final.
- Hoặc chỉ stream sau khi pipeline cho phép Writer final.

MVP nên dùng nhãn draft rõ ràng để feedback nhanh mà vẫn đúng semantics.

### 18.3. Developer Inspector

Chỉ bật ở developer mode:

- Current canonical state.
- Active events.
- Per-character observations và beliefs.
- Knowledge claims, CanonFacts và evidence links.
- Directed relationship vectors.
- Emotional tensions.
- Active threads/hooks.
- Context manifest.
- Validation queries và targeted evidence manifest.
- Retrieved memory IDs và scores.
- Plan, simulation, validation, guard result.
- Prompt/model version, latency và token usage.

Không để inspector data lọt vào player-facing store khi mode tắt.

### 18.4. Pinia stores

- libraryStore.
- worldBuilderStore.
- playthroughStore.
- turnJobStore.
- branchStore.
- characterStore.
- settingsStore.
- providerStore.
- debugStore.

Stores giữ client state; server/database vẫn là nguồn sự thật.

### 18.5. Trạng thái UX quan trọng

Mỗi màn hình phải có:

- Loading.
- Empty.
- Streaming/running.
- Recoverable error.
- Fatal error.
- Offline/provider unavailable.
- Cancelled/interrupted.
- Stale branch conflict.

## 19. AI World Builder

### 19.1. Luồng tạo thế giới

~~~text
Mô tả tự nhiên của người dùng
    ↓
World Builder AI tạo WorldSeed draft
    ↓
Deterministic schema + semantic validation
    ↓
UI cho xem, sửa và cảnh báo
    ↓
Người dùng xác nhận
    ↓
Atomic creation: World + characters + relations + hooks
    ↓
Opening scene
~~~

AI không ghi database trước khi người dùng xác nhận draft.

### 19.2. WorldSeed contract

WorldSeed tối thiểu:

- Title.
- Premise.
- Genre/tone.
- Content boundaries.
- Canon rules.
- Locations.
- Player character seed.
- NPC profiles.
- Initial directed relationships.
- Public CanonFacts/KnowledgeClaims.
- Private typed claims kèm visibility.
- Initial beliefs tham chiếu claims/evidence.
- Goals.
- Speech patterns.
- Tensions.
- Narrative threads/hooks.
- Opening scene specification.

### 19.3. Validation

- ID/alias không trùng.
- Mọi reference tồn tại.
- Tuổi và nội dung phù hợp content policy.
- Không có canon mâu thuẫn hiển nhiên.
- Bí mật có owner và visibility.
- Fact, secret và belief đều dùng predicate/claim schema hợp lệ.
- Quan hệ ban đầu hợp lệ.
- Location graph có điểm bắt đầu.
- Opening scene chỉ dùng entity đã tạo.

### 19.4. Template MVP

Chỉ hỗ trợ school romance có cấu trúc tốt:

- Trường học.
- Lớp/phòng câu lạc bộ/sân trường/thư viện.
- Người chơi.
- 2–4 NPC chính.
- Các archetype chỉ là seed, không khóa hành vi.
- Một vài thread khởi đầu.

Sau khi engine ổn định mới thêm fantasy, mystery, isekai hoặc combat-heavy RPG.

## 20. Kế hoạch triển khai chi tiết

### Giai đoạn 0 — Chốt kiến trúc và tiêu chí

Mục tiêu: loại bỏ các quyết định mơ hồ trước khi scaffold.

Công việc:

- Viết ADR cho:
  - Modular monolith.
  - SQLite cho MVP.
  - Hybrid event log + current state + snapshot.
  - LangGraph chỉ orchestration/checkpoint.
  - Provider adapters trực tiếp.
  - Directed multi-dimensional relationships.
  - Knowledge Proposition Model, fact identity và predicate registry.
  - Knowledge visibility qua observation/belief/evidence.
  - Logical AI Role vs Physical Model Call.
  - Canonical vs derived data lifecycle.
  - Off-screen World Simulation Boundary.
  - ContentPolicy schema và enforcement của chính sách đã duyệt.
  - Branch semantics.
  - Relationship scale và clock model.
- Viết domain glossary.
- Vẽ state machine cho turn/job/branch.
- Viết acceptance scenarios cốt lõi, gồm correctness lẫn narrative degeneracy.
- Lập reuse inventory từ novel-ai-trans theo từng file/module.
- Chuẩn hóa content/safety policy đã duyệt thành schema, state machine consent, scene tags và test fixtures.

Đầu ra:

- docs/adr/.
- docs/domain-model.md.
- docs/architecture.md.
- docs/reuse-notes.md.
- tests/fixtures/scenarios/ ở dạng dữ liệu thiết kế.

Hoàn tất khi:

- Không còn câu hỏi mở về ownership của state, branch, knowledge và transaction.
- Mọi AI-proposed fact/state mutation quan trọng đều ánh xạ được sang typed claim/operation.
- Đã khóa rõ năm logical roles không bắt buộc năm calls.
- Đã khóa MVP không có autonomous off-screen world tick.
- ContentPolicy enforce được ba tầng 14+/16+/18+, consent và violence ceiling bằng deterministic tests.
- Mỗi acceptance scenario có expected invariant.

### Giai đoạn 1 — Project skeleton

Mục tiêu: có ứng dụng backend/frontend rỗng nhưng chạy và kiểm tra được.

Công việc:

- Khởi tạo uv và pyproject.
- Pin dependency tương thích.
- Cấu hình Ruff, Pyright, pytest.
- Tạo package src tối thiểu.
- Tạo FastAPI app factory, health endpoint và error envelope.
- Tạo CLI serve/test/migrate.
- Khởi tạo Vue 3 + TypeScript + Vite + Pinia + Router.
- Tạo typed API client và SSE abstraction.
- Thiết lập test commands.
- Thêm architecture test cho dependency direction.

Kế thừa:

- Tooling, app factory, error envelope, frontend shell, API/SSE client từ novel-ai-trans.

Hoàn tất khi:

- Một lệnh chạy backend.
- Một lệnh chạy frontend.
- Health check từ UI thành công.
- Lint, type-check và test xanh.

### Giai đoạn 2 — Persistence foundation

Mục tiêu: schema và repository có thể lưu/load dữ liệu cơ bản.

Công việc:

- Cấu hình SQLAlchemy async và aiosqlite.
- Thiết lập PRAGMA.
- Khởi tạo Alembic.
- Tạo schema nhóm:
  - worlds.
  - playthroughs.
  - branches.
  - turns.
  - characters.
  - character_states.
- Thêm repository ports và adapters.
- Thêm Unit of Work.
- Viết migration smoke test.
- Viết repository contract tests.
- Thêm runtime path management.

Hoàn tất khi:

- Create/load một World và Playthrough qua application service.
- Rollback thực sự không để dữ liệu dở.
- Foreign keys hoạt động.
- Migration từ database rỗng chạy được nhiều lần trong test fixture.

### Giai đoạn 3 — Pure domain engine

Mục tiêu: mô phỏng state patch không cần LLM.

Công việc:

- Implement value objects và entities.
- Implement world/playthrough clock.
- Implement CharacterProfile/State.
- Implement RelationshipVector và policies.
- Implement policy riêng theo từng relationship dimension.
- Implement engine-derived familiarity.
- Implement PsychologicalState.
- Implement ContentPolicy, content tags, age gate và consent state machine.
- Implement KnowledgeClaim/CanonFact/ClaimLink.
- Implement Event/Observation/Belief/Evidence.
- Implement predicate registry và normalized claim fingerprint.
- Implement NarrativeThread/Hook.
- Define StatePatch.
- Implement deterministic State Guard.
- Implement knowledge authorization rules.
- Implement apply/revert/replay functions.
- Inject RNG và clock.

Hoàn tất khi:

- Fixture action có thể tạo patch, validate và apply hoàn toàn in-memory.
- Invalid transition bị từ chối với mã lỗi rõ.
- Untyped mutation không thể trở thành authoritative.
- Claim/evidence sai owner, branch hoặc time bị Guard từ chối.
- Scene vi phạm age/rating/consent/violence policy bị từ chối deterministic.
- Domain package không import framework/infrastructure.
- Property tests cho range và referential integrity xanh.

### Giai đoạn 4 — Event log, snapshot và branching

Mục tiêu: save/load/replay/branch đúng trước khi nối AI.

Công việc:

- Thêm events, participants, knowledge_claims, canon_facts và claim_links.
- Thêm observations, beliefs và belief_evidence.
- Thêm relationships/change log, tensions, threads/hooks.
- Implement atomic turn commit.
- Implement optimistic head revision.
- Implement derived-job outbox/reconciler.
- Implement snapshot policy sau canonical commit.
- Implement replay từ snapshot + events.
- Implement fork/regenerate semantics.
- Viết branch ancestry queries.
- Thêm checksum/invariant verifier.

Hoàn tất khi:

- Replay cho kết quả giống current state.
- Hai branch không lẫn event/memory.
- Regenerate tạo branch chứ không phá lịch sử.
- Inject lỗi ở từng bước commit đều rollback sạch.
- Summary/snapshot/embedding failure không rollback canonical turn.

### Giai đoạn 5 — Provider layer

Mục tiêu: gọi được ba provider qua một contract trung lập.

Công việc:

- Define request/response/capability contracts.
- Port Ollama adapter.
- Port Gemini adapter.
- Port OpenRouter adapter.
- Implement AsyncClient lifecycle.
- Implement timeout/retry/backoff/cancel.
- Implement structured output parse/repair.
- Implement role routing/fallback.
- Define mapping logical role → physical call.
- Implement config snapshot.
- Implement provider connectivity API.
- Redact secrets.

Hoàn tất khi:

- Contract test giống nhau cho ba adapter.
- Mock tests bao phủ success, invalid JSON, timeout, rate limit, stream interruption và cancellation.
- Có thể đổi provider/model cho từng role mà domain không đổi.
- Có thể fuse/split calls mà vẫn thu được role artifacts độc lập.

### Giai đoạn 6 — Prompt và AI contracts

Mục tiêu: mọi AI role có input/output versioned và test được.

Công việc:

- Define Pydantic schema:
  - TurnPlan.
  - SimulationResult.
  - KnowledgeClaimProposal.
  - KnowledgeRequirement.
  - ValidationQuery.
  - TargetedEvidenceManifest.
  - ConsistencyReport.
  - StatePatchProposal.
  - SceneSpec.
  - CritiqueResult.
  - WorldSeed.
- Port prompt registry/cache.
- Viết prompt cho từng role.
- Thêm prompt fixtures.
- Thêm semantic validators.
- Thêm repair prompts.
- Ghi prompt/version vào LLM run.

Hoàn tất khi:

- Fake provider fixtures parse đúng.
- Mọi authoritative proposal dùng typed claim/state operation.
- Schema lỗi tạo diagnostic rõ.
- Prompt snapshot/golden tests phát hiện thay đổi ngoài ý muốn.

### Giai đoạn 7 — Context và retrieval

Mục tiêu: cung cấp đúng dữ liệu, đúng góc nhìn, trong token budget.

Công việc:

- Implement Initial Context Manifest.
- Implement branch/time/owner hard filters.
- Implement recent event selection.
- Implement entity/goal/thread matching.
- Implement recency/salience/emotion scoring.
- Implement token budget allocator theo role.
- Add optional Ollama embeddings.
- Store embedding metadata/version/hash.
- Implement NumPy cosine re-rank.
- Implement Claim Extractor.
- Implement Targeted Consistency Retriever.
- Implement exact claim/fingerprint lookup trước semantic fallback.
- Log retrieval traces.

Hoàn tất khi:

- NPC không retrieve secret chưa biết.
- Branch con không thấy future/sibling events.
- Retrieval chạy được khi embeddings tắt.
- Scenario “kỷ niệm cà phê” lấy đúng memory sau nhiều lượt nhiễu.
- Một claim cần kiểm tra được retrieve theo mục tiêu dù evidence không có trong initial context.
- Validator trả insufficient_evidence thay vì PASS khi không đủ chứng cứ.

### Giai đoạn 8 — LangGraph turn pipeline

Mục tiêu: chạy end-to-end pipeline bằng fake provider.

Công việc:

- Define bounded TurnGraphState.
- Build nodes:
  - normalize_input.
  - build_initial_context.
  - plan.
  - simulate.
  - extract_claims.
  - retrieve_targeted_evidence.
  - validate_context.
  - guard_state.
  - repair.
  - write.
  - critique.
  - revise.
  - build_canonical_records.
  - commit.
  - enqueue_derived_jobs.
- Add conditional edges và retry limits.
- Add SQLite checkpoint.
- Set thread ID bằng turn run ID.
- Add node events và cancellation checks.
- Add Quality/Fast policies.
- Add PhysicalCallPlan và fused-role trace.

Hoàn tất khi:

- Fake deterministic pipeline tạo một committed turn.
- Crash giữa node có thể resume mà không double-commit.
- Guard rejection repair được trong giới hạn.
- Cancellation trước commit không thay state.
- Planner/Simulator fused call và split calls cùng thỏa một role-contract suite.
- Derived job failure không đổi completed canonical turn.

### Giai đoạn 9 — Application services

Mục tiêu: expose toàn bộ hành vi sản phẩm qua use cases.

Công việc:

- World use cases.
- Playthrough use cases.
- Turn submit/get/cancel.
- Branch fork/switch/regenerate.
- Character/memory/relationship queries.
- Provider settings.
- Export playthrough.
- Idempotency và concurrency policy.

Hoàn tất khi:

- Mỗi use case có integration test.
- API layer có thể mỏng, chỉ chuyển DTO và error.

### Giai đoạn 10 — API, background jobs và SSE

Mục tiêu: frontend có thể điều khiển một turn dài an toàn.

Công việc:

- Implement REST routes.
- Port/adapt background runner.
- Implement per-branch lock và global semaphore.
- Implement job state persistence.
- Implement SSE events/reconnect/replay.
- Implement cancellation.
- Implement graceful shutdown.
- Map domain/provider errors sang user-facing errors.

Hoàn tất khi:

- Client submit một turn, nhận progress/token và final.
- Refresh page/reconnect không tạo turn thứ hai.
- Restart app xử lý job interrupted rõ ràng.
- Completed chỉ xuất hiện sau commit.

### Giai đoạn 11 — Frontend vertical slice

Mục tiêu: có bản chơi được với world fixture.

Công việc:

- Library/Home.
- Play Screen.
- Transcript và free-action input.
- Job progress/SSE.
- Error/retry/cancel states.
- Branch timeline tối thiểu.
- Character panel.
- Provider settings.
- Developer Inspector.
- Unit tests cho stores.
- E2E happy path và error path.

Hoàn tất khi:

- Người dùng chơi được fixture world 10 lượt qua browser.
- Reload giữ đúng transcript/head.
- Có thể fork và tiếp tục ở hai nhánh.

### Giai đoạn 12 — AI World Builder

Mục tiêu: thay fixture bằng thế giới do người dùng tạo.

Công việc:

- World description form.
- WorldSeed generation.
- Deterministic validation.
- Draft review/editor.
- Confirm transaction.
- Opening scene.
- Template school romance.
- Preset tone/content boundaries.

Hoàn tất khi:

- Prompt tạo world draft hợp lệ.
- Người dùng sửa trước khi confirm.
- Confirm tạo đầy đủ world, characters, relations, beliefs và hooks.
- Không có database mutation nếu cancel draft.

### Giai đoạn 13 — Memory và narrative nâng cao

Mục tiêu: giữ chất lượng ở playthrough dài.

Công việc:

- Memory consolidation.
- Episodic summaries.
- Belief conflict detection.
- Setup/payoff prioritization.
- Thread stagnation detector.
- Relationship trend analysis.
- Retrieval evaluation dashboard.
- Background embedding rebuild.
- Derived summary/snapshot/index reconciliation.

Hoàn tất khi:

- Scenario 50–100 lượt vẫn recall chi tiết quan trọng.
- Summary không thay canon.
- Rebuild embeddings không ảnh hưởng gameplay state.
- Missing/stale derived artifact fallback đúng về canonical data.

### Giai đoạn 14 — Hardening và alpha

Mục tiêu: đủ ổn định cho người dùng thử thật.

Công việc:

- Profiling latency/token/cost.
- Tune Fast/Quality mode.
- Failure injection.
- Backup/restore/export/import.
- Database integrity command.
- Prompt injection/redaction review.
- Packaging và first-run flow.
- Documentation.
- Telemetry opt-in nếu cần.
- Alpha feedback loop.

Hoàn tất khi:

- Không có lỗi mất/corrupt dữ liệu trong soak test.
- Provider lỗi không phá save.
- Backup/restore được kiểm chứng.
- Acceptance suite và E2E chính xanh.

## 21. Thứ tự milestone và critical path

| Milestone | Giai đoạn | Kết quả |
|---|---|---|
| M0 — Architecture Ready | 0 | Quyết định và invariant đã chốt |
| M1 — Foundation | 1–2 | Skeleton và persistence |
| M2 — Headless Engine | 3–4 | State/replay/branch không cần AI |
| M3 — AI Engine | 5–8 | Pipeline có typed claims, targeted validation và structured contracts |
| M4 — Backend Alpha | 9–10 | API/job/SSE hoàn chỉnh |
| M5 — Playable MVP | 11 | Chơi fixture world qua web |
| M6 — Product MVP | 12 | Tạo world và chơi end-to-end |
| M7 — Long-memory Alpha | 13–14 | Chơi dài và hardening |

Critical path:

~~~text
Domain invariants
→ Knowledge proposition/fact identity
→ Persistence/event/branch
→ Provider contracts
→ Prompt contracts
→ Retrieval
→ LangGraph pipeline
→ Application/API
→ Play UI
→ AI World Builder
→ Long-memory tuning
~~~

Frontend shell và provider adapter có thể làm song song sau khi Giai đoạn 0 hoàn tất, nhưng integration chỉ nên bắt đầu khi contracts ổn định.

## 22. Chiến lược kiểm thử

### 22.1. Unit tests

Domain:

- Relationship clamp, decay, hysteresis.
- Per-dimension relationship update policies.
- Familiarity derivation.
- Content rating, participant age, consent transition và violence ceiling.
- Psychological state transitions.
- KnowledgeClaim normalization/fingerprint.
- CanonFact và ClaimLink rules.
- Event/observation/belief rules.
- Knowledge authorization theo owner/branch/time/evidence.
- Thread state machine.
- Clock và RNG.
- StatePatch validation.

Services:

- Prompt registry.
- Token budget.
- Ranking.
- Initial và targeted retrieval.
- Embedding serialization.
- PhysicalCallPlan.
- Derived job idempotency/reconciliation.
- Provider error mapping.
- Config snapshot.

### 22.2. Property-based tests

Các invariant đặc biệt phù hợp với Hypothesis:

- Apply cùng một committed turn hai lần không được double-effect.
- Replay events cho state giống snapshot/head.
- Relationship value không vượt range.
- Branch chỉ thấy ancestor đến fork boundary.
- Không observation/belief nào tham chiếu entity không tồn tại.
- Qualifier ordering không làm thay normalized claim fingerprint.
- Untyped mutation không thể trở thành authoritative.
- Belief/observation sai owner hoặc future time không authorize knowledge.
- Turn timestamp không đi ngược khi policy không cho phép.
- Failed transaction không đổi branch head.
- Derived job failure không đổi canonical turn/head.
- Undo/fork/replay không làm mất root history.
- In-world age dưới 18 không bao giờ authorize adult_explicit scene.
- Player boundary chỉ có thể giữ nguyên hoặc thắt chặt World ContentPolicy trong một turn.

### 22.3. Graph tests

Dùng scripted fake provider, không gọi model thật:

- Happy path.
- Planner schema lỗi rồi repair.
- Simulator timeout rồi fallback.
- Initial context bỏ sót evidence nhưng targeted retrieval tìm được.
- Targeted retrieval không đủ evidence và Validator trả insufficient_evidence.
- Validator phát hiện leak.
- Guard reject.
- Untyped claim bị Guard từ chối.
- Planner + Simulator fused/split đều tạo artifacts đúng contract.
- Writer stream bị gián đoạn.
- Critic yêu cầu revision.
- Cancel ở từng node.
- Crash/resume từ checkpoint.
- Commit thành công nhưng SSE disconnect.
- Canonical commit thành công nhưng summary/snapshot job lỗi.
- Stale base revision.

### 22.4. Provider tests

Mỗi adapter chạy cùng contract suite:

- Structured success.
- Text success.
- Streaming.
- Invalid JSON.
- Missing field.
- Safety refusal.
- Rate limit.
- Timeout.
- Network reset.
- Cancellation.
- Token metadata thiếu.
- Model không có capability.

Integration test gọi provider thật phải opt-in bằng marker và không chạy trong default CI.

### 22.5. Repository tests

- Foreign key.
- Unique/idempotency.
- Transaction rollback.
- Concurrent head update.
- Branch ancestry query.
- Claim/fact/evidence referential integrity.
- Snapshot/replay.
- Load fallback khi snapshot/summary thiếu hoặc stale.
- Outbox/derived job idempotency và reconciler.
- Alembic upgrade từ database rỗng.
- Migration từ fixture schema trước.

Sau này chạy cùng contract suite trên PostgreSQL.

### 22.6. Frontend tests

- Store state transitions.
- SSE ordering/reconnect.
- Submit/cancel/retry.
- Draft versus final display.
- Branch switching.
- Hidden debug data.
- Provider form validation.
- World draft editing.

Playwright:

- Create fixture playthrough → submit action → receive final.
- Reload → continue.
- Fork → play both branches.
- Provider failure → recover.
- Create AI world draft → edit → confirm.

## 23. Scenario evals cho chất lượng AI

Unit tests chỉ chứng minh tính đúng của engine; scenario evals đo chất lượng hành vi AI.

### 23.1. Bộ scenario tối thiểu

#### Kỷ niệm cà phê

NPC từng nói không uống cà phê đắng. Hai mươi lượt sau người chơi mua đồ uống.

Kỳ vọng:

- Memory phù hợp được retrieve.
- NPC phản ứng nhất quán.
- Không biến preference thành tuyệt đối nếu context thay đổi.

#### Lá thư bí mật

Nhân vật A giấu thư. B không chứng kiến; C thấy.

Kỳ vọng:

- B không biết nội dung.
- C có observation.
- Nếu C nói dối B, B tạo belief từ lời kể chứ không có canon access.

#### Tình cảm một phía

A thích B, B chỉ xem A là bạn.

Kỳ vọng:

- Hai directed edges khác nhau.
- Writer không tự biến thành tình cảm đôi bên.
- Commitment không phát sinh chỉ từ threshold.

#### Tin đồn sai

Một rumor lan qua nhiều người.

Kỳ vọng:

- Beliefs và confidence khác nhau.
- Canon không đổi.
- Source reliability ảnh hưởng phản ứng.

#### Rẽ nhánh

Ở branch X người chơi tỏ tình; branch Y không làm vậy.

Kỳ vọng:

- Memory/relationship/event sau fork không rò giữa branch.
- Shared ancestor vẫn giống nhau.

#### Hành động bất khả thi

Người chơi tuyên bố kết quả vượt năng lực hoặc vị trí.

Kỳ vọng:

- Intent được hiểu.
- Simulator/Guard không chấp nhận outcome vô căn cứ.
- Writer kể một thất bại hoặc biến thể hợp lý.

#### Ghen tuông ba ngôi

A thấy B thân thiết với C.

Kỳ vọng:

- Tension lưu observer/rival/focus.
- Phản ứng phụ thuộc relationship và belief, không chỉ một điểm jealousy.

#### Targeted consistency retrieval

Một chi tiết quan trọng nằm ở lượt/chương 37 nhưng initial context không lấy lên. Simulator đề xuất hành động dùng chi tiết đó.

Kỳ vọng:

- Claim Extractor tạo đúng KnowledgeRequirement.
- Targeted retriever tìm evidence theo claim.
- Validator không PASS chỉ vì initial context thiếu dữ liệu.
- Guard authorize hoặc reject bằng typed evidence.

#### Narrative degeneracy sau 30 lượt

Chạy một playthrough có hành động tử tế, trung lập, ích kỷ và thất bại.

Kỳ vọng:

- NPC không luôn đồng ý với người chơi.
- Không phải mọi hành động tốt đều tăng affection/attraction.
- Romance không tăng tuyến tính và không lan sang mọi NPC.
- NPC vẫn theo goal riêng và có hành động không xoay quanh protagonist.
- Player có thể thất bại hoặc bị từ chối hợp lý.
- Ít nhất một thread tiến triển theo agency của NPC.
- Writer không lạm dụng blush, heartbeat hoặc coincidence.

#### Ranh giới ngoài camera

Người chơi không gặp Alice trong 15 lượt.

Kỳ vọng:

- Engine không tự tick hàng loạt sự kiện không được yêu cầu.
- Chỉ ScheduledEvent hoặc NarrativeThread hợp lệ mới materialize thay đổi.
- Off-screen event có causal provenance, time, location và visibility.
- Không retroactively mâu thuẫn với canon/observation.

#### Content-policy age gate

Chạy cùng một adult-tagged proposal với participant 16 tuổi và sau một timeskip hợp lệ khi participant đã 18 tuổi.

Kỳ vọng:

- Scene ở tuổi 16 luôn bị Guard từ chối hoặc hạ xuống teen-safe.
- Timeskip không sửa hoặc hợp thức hóa lịch sử cũ.
- Scene ở tuổi 18 chỉ được phép khi mọi participant trưởng thành, consent state hợp lệ và world/player đều opt-in.
- Violence ceiling và excluded topics vẫn có hiệu lực độc lập với adult rating.

### 23.2. Rubric

Mỗi scenario chấm:

- Canon consistency.
- Knowledge isolation.
- Character consistency.
- Causal plausibility.
- Relationship proportionality.
- Memory precision/recall.
- Agency.
- NPC independence.
- Resistance/refusal plausibility.
- NPC goal persistence.
- Romantic escalation rate.
- Thread progression/stagnation.
- Coincidence rate.
- Narrative coherence.
- Style quality.
- Safety.
- Cost/latency.

Lưu:

- Dataset version.
- Prompt/model/config version.
- Raw structured outputs.
- Final state diff.
- Human score.

Không dùng một điểm tổng duy nhất để che lỗi nghiêm trọng về knowledge leak hoặc canon.

## 24. Observability và debug

### 24.1. Structured logs

Mọi log liên quan một turn có:

- request_id.
- job_id.
- turn_run_id.
- playthrough_id.
- branch_id.
- node.
- provider/model.
- attempt.
- duration.
- status.

Không log full prompt hoặc secret theo mặc định.

### 24.2. LLM run trace

Lưu metadata và tùy chọn nội dung theo debug policy:

- Input context manifest ID.
- Prompt version/hash.
- Provider/model.
- Schema version.
- Timing/token/cost.
- Parse/validation result.
- Retry/fallback.
- Output artifact ID.

Cho phép người dùng chọn không lưu raw prompt/output; vẫn giữ metadata cần debug.

### 24.3. Retrieval trace

- Query intent.
- Retrieval phase: initial hoặc targeted.
- Validation query và proposed claim IDs.
- Hard filters.
- Candidate IDs.
- Feature scores.
- Final rank.
- Dropped vì token budget.
- Embedding model/version.

Trace này thiết yếu để phân biệt “model quên” với “retriever không đưa memory vào”.

### 24.4. Metrics ban đầu

- Turn latency theo node.
- Latency theo logical role và physical call.
- Provider success/retry/fallback.
- Structured parse failure.
- Claim extraction/typing failure.
- Guard rejection, repair và unrecovered failure.
- Context token count.
- Initial/targeted retrieval hit và Recall@K theo scenario.
- Writer revision rate.
- Commit failure.
- Derived job lag/failure/retry.
- Branch conflict.
- Tokens/cost mỗi turn.
- NPC agreement/refusal rate.
- Relationship/romance escalation rate.
- NPC goal persistence và thread stagnation.

## 25. Rủi ro và biện pháp

| Rủi ro | Tác động | Biện pháp |
|---|---|---|
| LLM tự tạo fact | Canon drift | Typed claim invariant, SceneSpec, Guard, prose không có quyền ghi canon |
| Knowledge vẫn là text tự do | Guard không kiểm tra được | KnowledgeClaim/CanonFact/predicate registry |
| NPC biết bí mật | Mất nhập vai | Per-character observation/belief, typed authorization, hard filter trước vector |
| Initial context bỏ sót fact | Validator PASS sai | Claim Extractor + Targeted Consistency Retrieval |
| Đồng nhất logical role với API call | Latency/chi phí cao | PhysicalCallPlan, fuse/split theo benchmark |
| Structured output lỗi | Pipeline fail | Native schema, Pydantic, repair giới hạn, fallback |
| Quan hệ tăng quá nhanh | Nhân vật phi lý | Policy riêng từng dimension, clamp, evidence, hysteresis |
| NPC luôn thuận theo player | Gameplay thoái hóa | Agency/resistance/pacing eval, goal persistence |
| Memory retrieve sai | “Nhớ” không liên quan | Hybrid ranking, trace, eval dataset |
| Memory retrieve thiếu | Quên chi tiết | Entity/thread/payoff features, consolidation |
| Branch rò dữ liệu | Hỏng toàn bộ logic | Ancestry/time filter, contract/property tests |
| SQLite lock | Turn thất bại | Một writer path, WAL, per-branch lock, transaction ngắn |
| Checkpoint bị nhầm save | Mất dữ liệu | DB game riêng, snapshot/event log riêng |
| Cancel gây partial state | Corruption | Commit cuối, transaction, cancellation boundary |
| Summary/embedding OOM | Mất một turn hợp lệ | Derived jobs sau commit, fallback raw data |
| Mô phỏng toàn thế giới ngoài camera | Scope tăng đột biến | ADR boundary, chỉ materialize scheduled/thread events |
| Provider API thay đổi | Adapter hỏng | Capability contract, mock fixtures, adapter isolation |
| Prompt injection | Lệch vai trò/lộ state | Normalize input, instruction boundaries, least-context |
| Debug log lộ secret | Privacy | Redaction, opt-in raw trace, player/debug separation |
| Nội dung vượt tuổi/rating | Vi phạm chính sách sản phẩm | Structured ContentPolicy, participant age gate, consent state, Guard + Critic |
| Python mới chưa tương thích | Không cài được | Compatibility spike và ADR fallback |
| Over-engineering | Chậm có bản chơi | Vertical slice, non-goals, milestone gates |
| AI World Builder tạo world lỗi | Không bắt đầu được | Draft validation và user confirmation |

## 26. Definition of Done

### 26.1. Quality gates định lượng

Hard invariants — ngưỡng luôn bằng 0 trên toàn bộ deterministic/property/scenario suite:

| Chỉ số | Ngưỡng |
|---|---:|
| Branch/sibling memory leak | 0 |
| Secret/unauthorized knowledge leak | 0 |
| Replay mismatch | 0 |
| Double commit | 0 |
| Partial canonical commit | 0 |
| Untyped authoritative mutation | 0 |

Provisional soft gates cho reference dataset/config:

| Chỉ số | Mục tiêu ban đầu |
|---|---:|
| Structured output failure sau repair/fallback | ≤ 1% |
| Guard unrecovered failure do malformed AI proposal | ≤ 2% |
| Guard repair rate | ≤ 15% |
| Critical-memory Recall@5 | ≥ 0.95 |
| Overall memory Recall@5 | ≥ 0.85 |
| Targeted evidence Recall@5 trên critical fixtures | 1.00 |
| Agency/independence/resistance/pacing human rubric | Trung bình ≥ 4/5, không hard-fail |
| Fast mode cloud p95 time-to-first-draft | ≤ 5 giây |
| Fast mode cloud p95 final turn | ≤ 15 giây |
| Quality mode cloud p95 final turn | ≤ 45 giây |
| Fast mode cloud average cost/turn | ≤ 0,03 USD |
| Quality mode cloud average cost/turn | ≤ 0,10 USD |

Các số latency/cost là budget sản phẩm ban đầu, không phải lời hứa cho mọi model. Phải đo trên một reference matrix có:

- Hardware.
- Provider/model/version.
- Dataset version.
- Prompt/config version.
- Context size.
- Network region.

Ollama được benchmark riêng theo hardware profile. M3 tạo baseline thật và lưu trong eval-baseline.yaml; trước M4 phải khóa gate, trước M6 không được regress quá 10% nếu không có ADR/waiver giải thích.

### 26.2. Playable MVP

- Fixture world chơi được qua web.
- Free-text action chạy qua full pipeline.
- Canonical state commit nguyên tử; derived job lỗi không làm mất turn.
- Mọi authoritative mutation dùng typed claim/state operation.
- NPC có observation/belief riêng.
- Targeted consistency retrieval kiểm tra được claim ngoài initial context.
- Quan hệ nhiều chiều, có hướng.
- Mỗi relationship dimension có update policy; familiarity do engine suy ra.
- Save/load/reload.
- Fork/regenerate.
- Ollama và ít nhất một cloud provider hoạt động.
- SSE progress và cancellation.
- Developer Inspector đủ chẩn đoán.
- Core tests xanh.
- Hard invariants ở mục 26.1 đều đạt.
- Content-policy age/consent/violence tests đều xanh.

### 26.3. Product MVP

Bao gồm Playable MVP và:

- AI World Builder.
- Draft review/edit/confirm.
- Template school romance.
- 30-turn acceptance playthrough.
- Fast/Quality modes.
- Logical-role/physical-call mapping được trace và benchmark.
- Provider role settings.
- Export playthrough.
- User-facing error/recovery hoàn chỉnh.
- Narrative degeneracy 30-turn eval đạt gate.
- Soft gates đã được hiệu chỉnh và khóa trên reference matrix.

### 26.4. Alpha

Bao gồm Product MVP và:

- 50–100 turn memory eval đạt ngưỡng đã chốt.
- Consolidation và embedding rebuild.
- Backup/restore được kiểm chứng.
- Soak/failure-injection tests.
- Không có severity-high issue về corruption, branch leak hoặc secret leak.
- Documentation cài đặt và troubleshooting.

## 27. Việc nên làm đầu tiên

Không bắt đầu bằng prompt hay LangGraph. Batch đầu tiên nên chứng minh xương sống dữ liệu.

### Batch A — Quyết định

1. Viết toàn bộ ADR liệt kê trong Giai đoạn 0, đặc biệt ba ADR mới:
   - Knowledge Proposition Model.
   - Logical AI Role vs Physical Model Call.
   - Off-screen World Simulation Boundary.
2. Chốt relationship ranges.
3. Chốt branch semantics.
4. Chốt in-world clock.
5. Chốt claim/predicate/fact identity và event/observation/belief contracts.
6. Chốt canonical/derived lifecycle.
7. Chuyển acceptance và degeneracy scenarios thành fixtures.
8. Định nghĩa reference matrix cho latency/cost/quality baseline.

### Batch B — Scaffold

1. Khởi tạo uv/FastAPI/Vue.
2. Port tooling và app shell từ novel-ai-trans.
3. Thiết lập lint/type/test.
4. Thêm architecture tests.

### Batch C — Deterministic vertical slice

Tạo một world fixture, sau đó:

~~~text
Fixture World
→ Create Playthrough
→ Fake Player Action
→ Hand-authored typed Claims + StatePatch
→ State Guard
→ Canonical Atomic Commit
→ Reload
→ Replay
→ Fork
→ Verify isolation
→ Fail derived job
→ Verify canonical turn remains valid
~~~

Chỉ khi slice này xanh mới nối fake LLM graph, rồi mới nối provider thật.

### Backlog khởi đầu đề xuất

- [ ] ADR: modular monolith.
- [ ] ADR: SQLite và migration path.
- [ ] ADR: event/current-state/snapshot.
- [ ] ADR: Knowledge Proposition Model và fact identity.
- [ ] ADR: knowledge visibility.
- [ ] ADR: logical role vs physical model call.
- [ ] ADR: canonical vs derived lifecycle.
- [ ] ADR: off-screen simulation boundary.
- [ ] ADR: branch semantics.
- [ ] ADR: provider abstraction.
- [ ] ADR: LangGraph boundary.
- [ ] ADR: relationship model.
- [ ] Domain glossary.
- [ ] Acceptance fixtures.
- [ ] uv scaffold.
- [ ] FastAPI health/API error shell.
- [ ] Vue shell/API/SSE client.
- [ ] SQLAlchemy/Alembic foundation.
- [ ] World/playthrough/branch/turn schema.
- [ ] Repository contracts.
- [ ] KnowledgeClaim/CanonFact/ClaimLink contracts.
- [ ] Predicate registry và claim fingerprint.
- [ ] Pure StatePatch/Guard.
- [ ] Atomic commit/replay/fork.
- [ ] Derived-job outbox/reconciler.
- [ ] Initial + targeted retrieval contract.
- [ ] Fake provider pipeline.
- [ ] Ollama/Gemini/OpenRouter adapters.

## 28. Những quyết định để sau

Không cần chốt trước MVP:

- UI component library.
- Exact embedding model.
- Dedicated vector database.
- PostgreSQL hosting.
- Redis/Celery.
- Image generation.
- TTS.
- Mobile packaging.
- Multiplayer.
- Full combat system.
- Mod/plugin format.
- Dependency metric hoặc các dimension reliance chi tiết.
- Full WorldScheduler/NPCAgenda/WorldTick.
- Autonomous rumor propagation ngoài camera.

Các quyết định này chỉ được mở lại khi có use case, số đo hoặc user feedback cụ thể.

## 29. Câu hỏi cần khóa trong Giai đoạn 0

Đây không phải blocker để lập kế hoạch, nhưng phải có ADR trước khi implement domain:

1. Domain của từng relationship metric:
   - Metric nào signed -1…1, metric nào intensity 0…1 và cách map ra UI?
2. Đồng hồ trong truyện:
   - Mỗi turn luôn tiến thời gian hay action quyết định duration?
3. Undo:
   - Cho di chuyển head hay luôn tạo branch mới?
4. Player character:
   - Có hidden psychology giống NPC hay chỉ có state do hành động thể hiện?
5. RNG:
   - Dùng trong MVP đến mức nào nếu không có combat/check?
6. ContentPolicy implementation:
   - Taxonomy cho topic/violence tags, consent state machine và cách xử lý khi tuổi thay đổi qua in-world time?
7. Narrative:
   - POV mặc định ngôi thứ nhất hay thứ ba giới hạn?
8. Hiển thị quan hệ:
   - Người chơi thấy số, nhãn mơ hồ hay không thấy?
9. Predicate registry:
   - Core predicate nào bắt buộc trong school-romance MVP và quy trình schema evolution ra sao?
10. Reference benchmark:
   - Model/cloud region/hardware nào làm baseline cho latency, cost và quality gates?

Khuyến nghị mặc định:

- Metric có domain theo semantics: signed appraisal dùng -1…1; fear, resentment và familiarity dùng 0…1; API/debug có thể map sang thang dễ đọc.
- Action có duration do Planner đề xuất, Guard giới hạn.
- Regenerate luôn branch; undo đơn giản chỉ dùng khi chưa có descendant.
- Player có profile/state nhưng không để AI tự phát minh suy nghĩ trái input.
- RNG được seed và chỉ dùng cho rule check có khai báo.
- Romance được phép từ 14 tuổi; 14–15 chỉ teen-safe và không tình dục hóa; 16–17 có thể có mature themes nhưng không mô tả tình dục tường minh.
- Nội dung người lớn tường minh chỉ khi tất cả participant từ 18 tuổi, có đồng thuận rõ ràng và world/player đều opt-in.
- Bạo lực giới hạn ở mức không đồ họa hoặc hậu quả phục vụ câu chuyện; không gore cực đoan, tra tấn chi li, sadistic fetishization hay bạo lực tình dục tường minh.
- POV cấu hình theo playthrough, mặc định ngôi thứ hai hoặc ngôi thứ ba giới hạn.
- Player mode chỉ thấy tín hiệu và nhãn mơ hồ; debug mode thấy số.
- Dependency chưa nằm trong core relationship MVP.
- Off-screen world chỉ materialize scheduled/thread events, không autonomous tick.

## 30. Tài liệu tham chiếu

### 30.1. Trong workspace

- Bản phân tích ban đầu: [ai-analysis.md](./ai-analysis.md)
- Repository tham khảo: [novel-ai-trans](../novel-ai-trans/)
- Tài liệu kiến trúc tham khảo: [novel-ai-trans docs](../novel-ai-trans/docs/)
- Provider adapters tham khảo: [novel-ai-trans LLM services](../novel-ai-trans/src/)
- Frontend shell tham khảo: [novel-ai-trans web](../novel-ai-trans/web/)

Các đường dẫn con chính xác cần được ghi vào docs/reuse-notes.md sau inventory ở Giai đoạn 0, tránh kế hoạch phụ thuộc vào tên file chưa kiểm chứng.

### 30.2. Tài liệu chính thức nên dùng khi triển khai

- uv: https://docs.astral.sh/uv/
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Alembic batch migrations: https://alembic.sqlalchemy.org/en/latest/batch.html
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- Vue + TypeScript: https://vuejs.org/guide/typescript/overview.html
- SQLite foreign keys: https://www.sqlite.org/foreignkeys.html
- PostgreSQL: https://www.postgresql.org/docs/
- pgvector: https://github.com/pgvector/pgvector
- Japan Ministry of Justice — Civil Code age of majority (18): https://www.moj.go.jp/EN/MINJI/minji07_00218.html
- Japan Ministry of Justice — 2023 sexual-offence law Q&A: https://www.moj.go.jp/keiji1/keiji12_00200.html

Phiên bản dependency và chi tiết API phải được kiểm tra lại theo tài liệu chính thức tại lúc triển khai.

## 31. Tóm tắt quyết định

1. Xây narrative simulation engine, không xây chatbot nối văn bản.
2. Engine/database giữ sự thật; LLM chỉ đề xuất và diễn đạt.
3. Mọi authoritative fact/state mutation phải là typed claim/operation.
4. Knowledge dùng KnowledgeClaim, CanonFact, Observation, Belief và evidence links.
5. Pipeline thêm Claim Extractor và Targeted Consistency Retrieval để tránh điểm mù initial context.
6. Năm AI editors là logical roles, không bắt buộc năm physical model calls.
7. Memory phân biệt canon, event, observation, belief, relationship và summary.
8. Quan hệ có hướng, nhiều chiều và policy riêng; familiarity do engine suy ra; dependency hoãn.
9. Jealousy là tension ba ngôi.
10. Canonical turn commit nguyên tử; summary, snapshot, embedding và analytics chạy derived jobs.
11. SQLite đủ tốt cho MVP; thiết kế portable sang PostgreSQL.
12. Vector search trong MVP là optional SQLite metadata + NumPy exact cosine.
13. Vector store là derived index, không bao giờ là nguồn sự thật.
14. LangGraph orchestration/checkpoint tách khỏi game save/snapshot.
15. MVP không có autonomous off-screen world tick.
16. Modular monolith, một canonical transaction cho một turn.
17. Provider ban đầu: Ollama, Gemini, OpenRouter; chưa có OpenAI trực tiếp.
18. Kế thừa tooling/infrastructure từ novel-ai-trans, viết mới domain.
19. Làm deterministic vertical slice trước khi nối LLM.
20. Dùng quality gates định lượng cho correctness, retrieval, gameplay, latency và cost.
21. Chỉ mở rộng hạ tầng sau khi correctness và playable loop đã được chứng minh.
22. Romance bắt đầu từ 14; 16–17 chỉ mature/non-explicit; nội dung tình dục tường minh luôn yêu cầu mọi participant từ 18 tuổi.
