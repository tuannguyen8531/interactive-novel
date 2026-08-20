# Interactive Novel

Local-first AI-powered interactive visual novel/RPG engine. The current alpha
includes the playable Vue application, AI turn pipeline, canonical SQLite
persistence, branching/regeneration/undo, hybrid memory retrieval, portable
import/export, backup/restore and developer diagnostics.

See [docs/status.md](docs/status.md) for the implementation matrix. The large
design document remains a roadmap, not a reliable progress tracker by itself.

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

## Provider configuration

Create the local environment file once:

```bash
cp .env.example .env
```

On the first launch, provider targets, model IDs, execution mode and routing are
seeded from `.env` into `runtime/settings.json`. The Settings / Providers screen
then edits this persisted configuration and applies it to the running provider
router when saved. Remove only `runtime/settings.json` to seed it from `.env`
again without deleting worlds or logs.
The model field discovers available IDs from the selected provider, while still
allowing a custom model ID when the catalog is unavailable or incomplete.

Provider calls are logged like `novel-ai-trans` under
`runtime/logs/YYYY-MM-DD/{request,response,error}.log`. Request and response logs
include the complete provider payloads for local debugging. Credentials and URL
query strings are redacted. Set `LOG_RETENTION_DAYS` to control daily-log
retention (default: 30 days). These logs may contain private story content and
should not be shared without review.

Developer Inspector is disabled by default on both sides. Enable the endpoint
with `INTERACTIVE_NOVEL_DEBUG=true`, then build the UI with
`VITE_ENABLE_INSPECTOR=true uv run build` when the Inspector is needed.

Keep `GEMINI_API_KEY`, `OPENROUTER_API_KEY` and other credentials in `.env`.
The UI stores only an environment-variable name such as `GEMINI_API_KEY`; API
responses and `runtime/settings.json` never contain the secret value. Shell
environment variables take precedence over `.env`.

Ollama uses separate defaults for generation and embeddings. Ensure the model
IDs selected in the UI exist locally (for example `llama3.2:3b` and
`nomic-embed-text:latest`). The default Ollama base URL includes its REST prefix:
`http://localhost:11434/api`.

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
uv run quality-report
```

`uv run test` follows the backend validation flow used by `novel-ai-trans`:
Ruff, Pyright and Pytest. Add `--frontend` to run the Vue unit tests in the
same invocation. Extra Pytest arguments go after `--`, for example
`uv run test -- --maxfail=1 -k health`.

`uv run quality-report` aggregates provider-real latency, token and estimated
cost samples from opt-in telemetry. It reports zero samples honestly until
`TELEMETRY_ENABLED=true` has been used for real turns.

`uv run migrate` upgrades the canonical database at `runtime/game.db`. Use
`uv run migrate --database /path/to/game.db` for a test or alternate runtime.
The separate `runtime/checkpoints.db` path is reserved for LangGraph execution
state and is not a save-game database.

Each saved playthrough has an **Export** action; the **Data** screen provides
portable story import, verified database backup/restore and the alpha feedback
form. CLI equivalents and opt-in telemetry are documented in
[docs/operations.md](docs/operations.md).
