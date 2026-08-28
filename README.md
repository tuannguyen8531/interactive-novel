# Interactive Novel

[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/)
[![Node.js 20+](https://img.shields.io/badge/node-20%2B-green.svg)](https://nodejs.org/)
[![uv](https://img.shields.io/badge/package%20manager-uv-2b2b2b.svg)](https://docs.astral.sh/uv/)

Local-first AI-powered interactive visual novel/RPG engine. It is a narrative
simulation system rather than a simple chat transcript: the engine owns
canonical world state, typed claims, events, relationships, memory, branches,
and turn history while AI components propose and express outcomes.

```text
World + player action
    -> turn graph and scoped memory retrieval
    -> deterministic validation and state guard
    -> canonical SQLite commit
    -> Vue play screen through REST/SSE
```

## Highlights

- Build and validate playable worlds with the World Builder and story templates.
- Run an AI-assisted turn pipeline with Planner, Simulator, Validator, Writer,
  and Critic roles behind typed contracts.
- Keep canonical game state in SQLite with event history, snapshots, branches,
  fork, regenerate, undo, and replay support.
- Use hybrid memory retrieval with knowledge visibility, provenance, and
  rebuildable derived indexes.
- Export and import playthroughs, create verified database backups, and restore
  them atomically through the CLI or Data screen.
- Use Ollama locally or Gemini and OpenRouter in the cloud, with configurable
  role routing, fallback, privacy settings, and opt-in telemetry.
- Open a deterministic frontend fixture without an LLM provider for local UI
  development and the ten-turn acceptance loop.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm for the Vue frontend
- One supported provider for server-backed AI turns:
  [Ollama](https://ollama.com/), [Gemini](https://aistudio.google.com/apikey),
  or [OpenRouter](https://openrouter.ai/keys)

The deterministic **Open fixture** flow does not require a configured provider.

## Quick start

From the project directory:

```bash
uv sync
cp .env.example .env
uv run doctor
uv run migrate
uv run build
uv run serve
```

Open <http://127.0.0.1:8000>. The health endpoint is
<http://127.0.0.1:8000/api/health>. Use **Open fixture** for a provider-free
local run, or configure a provider before creating a server-backed playthrough.

`uv run doctor` creates the runtime directories and checks readiness without
calling a provider. The canonical database is `runtime/game.db`; LangGraph
execution checkpoints are kept separately in `runtime/checkpoints.db`.

## Use the web GUI

For frontend hot reload, use two terminals:

```bash
# terminal 1: backend
uv run serve

# terminal 2: Vite frontend
cd web
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. The Vite server proxies `/api` to the backend.
`uv run serve` does not start Vite; it serves the production bundle from
`web/dist` after `uv run build`.

## Commands

| Command | Purpose |
| --- | --- |
| `uv run doctor` | Check readiness and create runtime directories |
| `uv run migrate` | Upgrade the canonical SQLite database |
| `uv run build` | Build the Vue production bundle |
| `uv run serve` | Start the API and built web application |
| `uv run test` | Run Ruff, format checks, Pyright, Pytest, and Vue unit tests |
| `uv run test --no-frontend` | Run backend validation without Vue unit tests |
| `uv run backup integrity` | Run SQLite integrity check |
| `uv run backup create --output <path>` | Create and verify a database backup |
| `uv run backup restore --input <path> --database <path>` | Verify and restore a backup |
| `uv run quality-report` | Report opt-in provider latency, token, and cost samples |

Extra Pytest arguments go after `--`, for example:

```bash
uv run test -- --maxfail=1 -k health
```

## Configuration and privacy

Copy `.env.example` to `.env` and keep provider credentials there. On first
launch, provider targets, model IDs, execution mode, and routing are seeded into
`runtime/settings.json`; the Settings / Providers screen can then edit the
persisted configuration. Remove only that file to seed it again without
deleting worlds or logs.

The UI and `runtime/settings.json` store provider choices and environment
variable names, never secret values. Shell environment variables take
precedence over `.env`. Keep `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, and other
credentials out of frontend code, prompts, SSE events, and logs.

Provider request, response, and error payloads are logged under
`runtime/logs/YYYY-MM-DD/`. Credentials and URL query strings are redacted, but
logs may still contain private story content. Review them before sharing and
use `LOG_RETENTION_DAYS` to control daily-log retention.

The Developer Inspector is disabled by default. Enable it for a session with
`INTERACTIVE_NOVEL_DEBUG=true`, then build the UI with
`VITE_ENABLE_INSPECTOR=true uv run build`.

## Validation

Apply safe Ruff fixes and formatting, then run the full validation pipeline:

```bash
uv run test --fix
uv run test
```

After frontend changes, also run:

```bash
uv run build
```

## Documentation

| Guide | Contents |
| --- | --- |
| [Operations](docs/operations.md) | Setup, backup/restore, providers, and telemetry |
| [Architecture](docs/architecture.md) | Module ownership, data authority, and dependency direction |
| [Domain model](docs/domain-model.md) | World, turn, event, knowledge, relationship, and branch contracts |
| [Content policy](docs/content-policy.md) | Age, consent, privacy, and violence boundaries |
