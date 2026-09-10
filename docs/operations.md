# Alpha operations

## First launch

From the project directory:

```bash
uv sync
uv run doctor
uv run migrate
uv run build
uv run serve
```

`doctor` only creates the runtime directories and checks readiness; it does not
call a provider. Canonical data lives in `runtime/game.db`, while LangGraph
checkpoints are kept separately in `runtime/checkpoints.db`. After `uv run
build`, the backend serves the built SPA at `http://127.0.0.1:8000`; `/api`,
`/docs`, and `/openapi.json` remain separate backend routes.

For frontend hot reload, use two terminals:

```bash
# terminal 1
uv run serve

# terminal 2
cd web && npm run dev
```

Run the standard project validation pipeline:

```bash
uv run test
uv run test --no-frontend
```

By default, the command runs Ruff, Pyright, Pytest, frontend ESLint, and the Vue unit tests;
`--no-frontend` skips all frontend checks for backend-only validation, while `--no-frontend-lint`
skips only frontend ESLint. If an
API test does not return after 30 seconds in a sandbox, terminate the command
and rerun the remaining checks as described in [Sandbox testing](#sandbox-testing).

## Integrity and backup

Check the database:

```bash
uv run backup integrity
```

Create a consistent backup through the SQLite online-backup API:

```bash
uv run backup create --output runtime/exports/game.db.backup
```

Restore to an explicitly selected path:

```bash
uv run backup restore \
  --input runtime/exports/game.db.backup \
  --database runtime/game.db
```

The restore command checks the source integrity, writes to a temporary file,
checks the destination, and only then replaces it atomically. Keep a backup
outside the runtime directory before restoring the active database.

A normal JSON playthrough export is available at
`GET /api/playthroughs/{id}/export`. The `.../export/bundle` endpoint adds a
checksum; `POST /api/exports/validate` checks the checksum and scope;
`POST /api/exports/import` performs an exact restore of a checksummed bundle by
rebuilding opening records and replaying each typed patch through the canonical
commit path. Import rejects an existing ID, so remove the old world before
restoring that same bundle. The corresponding UI is **Data → Import bundle**.

The **Data** page can also create, list, and restore backups. The API accepts
only safe filenames inside `runtime/exports`; arbitrary filesystem paths are
rejected. During restore, turn workers stop, the connection pool closes, the
file is replaced atomically, and new workers start afterward.

## Providers, telemetry, and security

- Provider failures are converted into safe errors and must not lose the
  canonical save; fallback runs only for errors that permit it.
- Telemetry is disabled by default. Only `TELEMETRY_ENABLED=true` creates
  `runtime/logs/telemetry.jsonl`; it contains latency, token counts, estimated
  cost, and provider metadata, not prompts or outputs.
- Every provider call is logged by day in
  `runtime/logs/YYYY-MM-DD/request.log`, `response.log`, and `error.log`.
  Request and response logs contain the complete payload sent to and received
  from the provider; credentials and query strings are redacted. Logs may
  contain private story content, so review them before sharing. Retention is
  controlled by `LOG_RETENTION_DAYS` (30 days by default).
- `INTERACTIVE_NOVEL_DEBUG` and `VITE_ENABLE_INSPECTOR` are disabled by
  default. To use the Inspector, enable the backend and then build the
  frontend with the Vite flag. Never put an API key in the frontend, prompts,
  SSE events, or logs.
- Player input is bounded, normalized, and labeled untrusted; prompt-injection
  flags do not turn it into a system or developer instruction.
- `STORY_LANGUAGE` seeds the Story language setting on first launch. The
  Settings / Providers screen can change the default for newly generated worlds;
  each confirmed world stores its own language so existing stories remain
  stable. Supported values are `en` and `vi`.

## Alpha feedback loop

Users can submit a rating and comment through `POST /api/feedback`. Feedback is
size-limited, common secrets are redacted, and the result is written to
`runtime/logs/feedback.jsonl`; this is opt-in private data, not canonical
memory.

The corresponding form is on the **Data** page.

## Quality gates and benchmarks

- Frontend fixture acceptance runs 30 turns in Vitest.
- The persistence soak commits and replays 100 turns and checks the branch head
  and invariants.
- The memory gate runs 100 turns and checks consolidation plus critical-memory
  Recall@5 = 1.00 across multiple time windows.
- Canonical failure injection runs through every transaction step and confirms
  that rollback leaves no partial turn.
- `uv run quality-report` aggregates real-provider telemetry by turn. It does
  not fabricate measurements when no telemetry sample exists.

Browser E2E with Playwright is intentionally deferred to avoid adding browser
 binaries and heavy dependencies; API integration, Vue store acceptance, and
 the production build remain part of the normal validation surface.

The 30-turn gate currently proves that the interaction flow and state do not
degrade. Model prose and narrative quality are environment-bound gates: choose
and lock a provider, model, and hardware before recording a baseline; do not
infer it from deterministic fixtures.

## Sandbox testing

Persistence and API tests may depend on SQLite lifecycle behavior or a provider.
When an API test does not return after 30 seconds in a sandbox, terminate the
test, skip the stuck API group, and record that fact in the report:

```bash
uv run test -- --ignore=tests/api
```

Do not repeatedly retry the same sandbox-only hang or download new packages
without permission. Do not treat the hang as an application failure unless it
also reproduces outside the sandbox.
