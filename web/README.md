# Interactive Novel web client

The Phase 11 vertical slice uses Vue 3, TypeScript, Pinia, Vue Router and the
typed REST/SSE client under `src/api/`.

```bash
npm run dev
```

Open the local Vite URL and choose **Open fixture**. The fixture is deterministic
and local-only: it supports ten turns, reload persistence, progress events,
cancel/retry states and branch fork/switch without requiring Ollama. When a
server playthrough is selected, the same screen uses the Phase 10 REST/SSE
routes and keeps the server export as its source of truth.

Validation commands:

```bash
npm run build
npm run test:unit
```

Set `VITE_API_BASE_URL` when the API is not served through the Vite proxy.
