# Interactive Novel

Local-first AI-powered interactive visual novel/RPG engine. Phase 2 adds the
SQLite persistence foundation without coupling the domain layer to SQLAlchemy.

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
uv run migrate
cd web && npm run test:unit
```

`uv run migrate` upgrades the canonical database at `runtime/game.db`. Use
`uv run migrate --database /path/to/game.db` for a test or alternate runtime.
The separate `runtime/checkpoints.db` path is reserved for LangGraph execution
state and is not a save-game database.

Alpha operations, backup/restore, integrity checks and opt-in telemetry are
documented in [docs/operations.md](docs/operations.md).
