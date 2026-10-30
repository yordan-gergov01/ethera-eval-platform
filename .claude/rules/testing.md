# Testing

Source: Bible Part III "Testing", brief §9 "Testing", template test layout.

## Shape

- `tests/` mirrors the source tree: one test file per source file, mirrored names.
- Names: `test_<function>_<scenario>_<expected>`, or invariant-named for seals
  (`test_gate_fails_iff_regression_or_error`).
- Unit tests with fakes for external concerns; integration tests through the ASGI app, the
  real PostgreSQL and the real RabbitMQ (`docker-compose.test.yml`). A test that proves the
  function but not the wiring is vacuous.

## Required tests

- Every endpoint: happy path, validation (422), auth (401), permission (403), not found
  (404), and tenant isolation (C5, D-014).
- Every data-access function: tenant isolation (C5, D-014).
- Every instruction set of the demo target: golden-sample tests pinned to instruction-set
  version, schema and mock model.
- Every Metric: fails the bad cases and passes the good ones of its rubric, and reads only
  its declared evidence fields.
- Every mechanical guard: a negative case proving it fires.

## Mocks

Mock only external services and clocks: model catalogs, benchmark sources, the sandbox
launcher, broker failures, notification channels (fake HTTP server for Slack), time. Never
mock our own code within a module, Pydantic validation or pure functions.

## Fixtures

Self-contained, descriptive names, no shared mutable state; each integration test gets a
fresh database (`fresh_database`). No skipped tests without a slice reference; inside Docker
(`REQUIRE_INTEGRATION=1`) a missing database or broker fails, never skips.

## Coverage

- 100% on auth, authorization, tenancy and audit modules (separate gate).
- ≥ 90% on `evals/*/domain`.
- A repo-wide floor that never decreases (`.coverage-floor`).

## Web

Vitest for hooks, the API client, long polling, report ordering and label maps.

## Sealed oracles

Sealed test files are listed per slice in `specs/<slice>/SEALED.md` with SHA-256 hashes and
denied for editing in `.claude/settings.json`. They never change by one byte; implementers
add their own test files beside them.

## Mechanical checks

- `pytest` (strict markers, strict config, `xfail_strict`); `npm test`.
- Coverage gates in `.github/workflows/core.yml` and the `full-gate` skill.
- Sealed-file hash check in the `seal-oracle` and `full-gate` skills.
