# Scenario fixture contract

The files in this directory are design data: they do not call an LLM or write
to the database. Each scenario must include:

- `id`, `category`, `setup`, and `actions` or `stimulus`;
- `expected_invariants` for required assertions;
- `hard_failures` for outcomes that must never occur;
- `implementation_area` to identify the implementation area that parameterizes
  the fixture into a test.

`core_acceptance.json` covers the deterministic engine, repository/branch
behavior, and scenario evaluation. `claim_contracts.json` fixes the mapping
from AI proposals to typed claims and operations. `content_policy.json` holds
deterministic vectors for `ContentPolicy`. `reference_matrix.json` defines the
metadata required for quality, latency, and cost measurements; real
measurements must retain the dataset, prompt, model, and configuration version.

Fixtures are not canon for any particular world. Their IDs are stable test IDs,
and each test must create its own playthrough/branch namespace.
