# ADR-0005: Provider adapter REST trực tiếp

- Status: Accepted for MVP
- Date: 2026-08-13

## Bối cảnh

MVP cần Ollama, Gemini và OpenRouter, mỗi provider có capability và lỗi khác
nhau. Ràng buộc toàn hệ thống vào một ChatModel abstraction sẽ làm lộ
assumption của provider vào domain.

## Quyết định

Khai báo provider port trung lập với các năng lực:

```text
generate_structured(request, schema)
generate_text(request)
stream_text(request)
embed(texts)
close()
```

Adapter gọi REST async trực tiếp qua HTTP client. Capability matrix và role
routing quyết định năng lực nào được dùng. Mỗi response có provider, model,
role, request ID, prompt/schema version, timing, token usage, finish reason,
retry và fallback metadata.

Mặc định local-first. Cloud provider chỉ nhận nội dung khi người dùng bật rõ
routing cloud; API key lấy từ environment hoặc OS keyring, không trả lại client
và không ghi vào settings/narrative logs. MVP không có OpenAI provider trực tiếp.

## Invariant

- Provider adapter không import domain application policy để tự quyết canon.
- Retry chỉ cho lỗi transient; cancellation được truyền tới safe point.
- Structured response luôn qua schema parse/semantic validation/repair giới hạn.
- Fallback không đổi output contract và không dùng để lách safety refusal.
- Secret bị redact khỏi log, trace và error envelope.

## Hệ quả

Provider có thể thay model cho từng logical role mà domain không đổi. REST
adapter dễ mock bằng contract suite và có thể bổ sung provider sau.
