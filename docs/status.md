# Implementation status

Updated: 2026-08-20

This file is the concise implementation tracker. `docs/plan.md` remains the
product and architecture roadmap.

| Area | Status | Evidence / notes |
|---|---|---|
| World Builder and playable turn loop | Complete | Real REST/SSE backend, editable draft and canonical confirmation |
| Save/load, fork and switch | Complete | Server-persisted active branch, canonical replay, ancestry visibility and repeated-undo tests |
| Regenerate | Complete | Dedicated API/UI; creates a branch before the selected turn and resubmits its action |
| Undo | Complete | Dedicated API/UI; activates a history-preserving branch at the parent turn |
| Portable export/import | Complete | Checksummed bundle download and exact restore; collision-safe refusal |
| Database backup/restore | Complete | CLI and Data UI, integrity check and atomic SQLite replacement |
| Alpha feedback | Complete | Secret-redacted JSONL endpoint and Data UI form |
| Developer Inspector | Complete | Canonical state, character memory, relationships, retrieval traces, invariants and opt-in LLM telemetry |
| Turn recovery | Complete | Durable-job discovery, SSE cursor reconnect and server-idempotent retry |
| Provider logging | Complete | Full redacted request/response payloads are written to daily local logs |
| 30-turn acceptance | Complete | Deterministic Vue vertical-slice gate |
| 50–100-turn memory | Complete | 100-turn consolidation plus critical-memory Recall@5 = 1.00 gate |
| Narrative quality eval | Environment-bound | The deterministic 30-turn path is gated; model quality still requires a chosen provider/model baseline |
| Soak/failure injection | Complete | 100-turn SQLite soak plus per-commit-step rollback injection |
| Latency/token/cost tooling | Complete | `uv run quality-report`; provider-real samples require opt-in telemetry |
| Provider-real baseline | Environment-bound | No result is fabricated when telemetry has zero samples |
| Browser E2E | Deferred by decision | Playwright/browser binaries intentionally omitted; API integration and Vue acceptance remain |

Current validation baseline:

- Ruff and Pyright clean.
- 206 backend tests passing.
- 36 frontend tests passing.
- Vue production build passing.

Update this file whenever a workflow or gate changes; do not infer progress from
phase headings in `docs/plan.md`.
