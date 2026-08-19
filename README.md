# Interactive Novel

Local-first AI-powered interactive visual novel/RPG engine. Phase 2 adds the
SQLite persistence foundation without coupling the domain layer to SQLAlchemy.

## Development

Requirements: Python 3.14+, `uv`, Node.js 20+ and npm.

```bash
uv sync
uv run build
uv run serve
```

After `uv run build`, `uv run serve` serves the built Vue SPA and backend from
`http://127.0.0.1:8000`. The health endpoint is
`http://127.0.0.1:8000/api/health`.

For frontend development:

```bash
uv run serve # terminal 1, backend
cd web
npm install
npm run dev
```

The Vite development server runs at `http://127.0.0.1:5173` and proxies
`/api` to the backend. `uv run serve` does not start Vite; it serves `web/dist`
after the production build.

Validation commands:

```bash
uv run test
uv run test --frontend
uv run test --fix
uv run build
uv run migrate
```

`uv run test` follows the backend validation flow used by `novel-ai-trans`:
Ruff, Pyright and Pytest. Add `--frontend` to run the Vue unit tests in the
same invocation. Extra Pytest arguments go after `--`, for example
`uv run test -- --maxfail=1 -k health`.

`uv run migrate` upgrades the canonical database at `runtime/game.db`. Use
`uv run migrate --database /path/to/game.db` for a test or alternate runtime.
The separate `runtime/checkpoints.db` path is reserved for LangGraph execution
state and is not a save-game database.

Alpha operations, backup/restore, integrity checks and opt-in telemetry are
documented in [docs/operations.md](docs/operations.md).
