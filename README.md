# Interactive Novel

Local-first AI-powered interactive visual novel/RPG engine. Phase 1 provides a
minimal FastAPI backend, Vue 3 frontend shell, typed REST client and SSE
abstraction.

## Development

Requirements: Python 3.14+, `uv`, Node.js 20+ and npm.

```bash
uv sync
uv run serve
```

The backend listens on `http://127.0.0.1:8000`; the health endpoint is
`http://127.0.0.1:8000/api/health`.

For frontend development:

```bash
cd web
npm install
npm run dev
```

Validation commands:

```bash
uv run test
uv run build
cd web && npm run test:unit
```

`uv run migrate` is currently a Phase 1 no-op. Persistence belongs to Phase 2.
