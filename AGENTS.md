# Project instructions

## Project

`interactive-novel` is a local-first AI-powered interactive visual novel/RPG
engine. Python code lives under `src/`, the Vue frontend under `web/`, and tests
mirror the backend layers under `tests/` while frontend tests live under
`web/src/tests/`.

Canonical world, playthrough, branch, turn, event, and memory data belongs in
`runtime/game.db`. LangGraph execution checkpoints belong in the separate
`runtime/checkpoints.db`. Settings, exports, logs, telemetry, and feedback are
also runtime data and must not be committed.

## Implementation conventions

- Target Python 3.14 and keep code compatible with the Ruff, Pyright, pytest,
  and dependency versions configured in `pyproject.toml` and `uv.lock`.
- Use `src.config.get_settings()` for application settings and
  `src.paths.get_runtime_paths()` for runtime filesystem locations.
- Keep domain rules and invariants in `src/domain/`; application use cases,
  contracts, ports, and transaction boundaries in `src/application/`;
  integrations in `src/services/`; REST/SSE adapters in `src/api/`; and CLI
  orchestration in `src/cli/`.
- Keep canonical game state separate from LangGraph state and derived artifacts.
  Derived indexes, summaries, embeddings, and analytics must never become the
  source of truth or invalidate a successful canonical turn.
- Use Pydantic models for API, provider, and AI contracts. Use dataclasses for
  domain and application value objects when they make ownership explicit.
- Route provider access through the LLM service boundaries. Preserve timeout,
  retry, cancellation, request metadata, privacy routing, and secret redaction.
- Load prompts through the prompt registry under `src/prompts/`; keep prompt
  versions, schemas, and template hashes explicit rather than embedding prompt
  text in graph nodes.
- Put tests in the directory matching the source layer. Mock provider, HTTP,
  and browser integrations; use `tmp_path` for filesystem behavior.

## Development

Requirements: Python 3.14+, `uv`, Node.js 20+, and npm.

```bash
uv sync
uv run doctor
uv run migrate
uv run build
uv run serve
```

For frontend hot reload, run `uv run serve` in one terminal and, from `web/`,
run `npm install` once and `npm run dev` in another terminal. The production
build is served by the backend from `web/dist`.

Keep provider credentials in `.env` copied from `.env.example`. The UI and
`runtime/settings.json` may store provider names and environment-variable names,
but must never contain secret values. Debug Inspector features are opt-in via
`INTERACTIVE_NOVEL_DEBUG=true` and `VITE_ENABLE_INSPECTOR=true`.

## Validation

Run the standard validation pipeline:

```bash
uv run test
```

Apply safe Ruff fixes and formatting before validation when appropriate:

```bash
uv run test --fix
```

Use `uv run test --no-frontend` for backend-only validation. Extra pytest
arguments go after `--`, for example:

```bash
uv run test -- --maxfail=1 -k health
```

Run the frontend checks directly after changes under `web/` when useful:

```bash
cd web
npm run test:unit
npm run build
```

### API tests in the sandbox

Some tests under `tests/api/` may hang in a restricted sandbox because of
SQLite or application-lifecycle behavior. If the standard command stalls for
30 seconds during API tests, terminate it and rerun:

```bash
uv run test -- --ignore=tests/api
```

Do not repeatedly retry a sandbox-only hang. Report the skipped API tests and
continue to run the remaining checks; do not treat the hang as an application
failure unless it also reproduces outside the sandbox.

## Documentation

Use `docs/operations.md` for setup, backup/restore, providers, telemetry, and
validation notes. Use `docs/architecture.md`, `docs/domain-model.md`, and
`docs/content-policy.md` as the core technical and product contracts. Keep
operational commands aligned with the CLI in `src/cli/` and avoid adding
roadmap or progress-tracking documents when a focused contract update is enough.
