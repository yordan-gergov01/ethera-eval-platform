---
name: full-gate
description: Run the Bible Phase 8 full clean gate for the whole repository — fresh probe database, repo-wide lint/format/types/import contracts, full suites, coverage gates, web check and build, sealed-file hashes — with durable logs, DONE markers and a stall watchdog. Outputs one table of every check with its numbers.
---

# Full clean gate

A run is DONE only when this whole gate passes. Targeted green never substitutes for it.

## Before starting

- **Windows paths:** pass Python tools (pytest-cov, coverage, scripts) a relative path or a
  Windows path (`cygpath -w`), never a Git Bash `/d/...` path — Python cannot create it, and
  pytest then exits 3 after the tests passed (seen 2026-10-29; the report was re-rendered
  from the same run's `.coverage` data).

- Check the environment first: nothing else writing to the test stack, no leftover test
  containers, machine not under heavy load. A red is diagnosed as a regression only after the
  environment is ruled out (isolation + a calm rerun).
- Logs go to `.gate/<timestamp>/` (gitignored). Every step writes `<step>.log` and ends with
  `echo "DONE exit=$?" >> <step>.log`.

## Steps (from the repository root)

1. **Fresh probe stack**: `cd ethera-eval-core && docker compose -f docker-compose.test.yml -p
   ethera_eval_gate up -d --wait postgres rabbitmq` with `TEST_DB_PORT`/`TEST_BROKER_PORT`
   set to free ports; the database is created from zero (tmpfs) and migrated by the suite.
2. **Core static** (venv active): `ruff format --check .`, `ruff check .`, `mypy`,
   `lint-imports`.
3. **Core suite with coverage** (background, durable log):
   `REQUIRE_INTEGRATION=1 pytest -p no:cacheprovider --cov --cov-report=term
   --cov-report=json:../.gate/<ts>/coverage.json`.
4. **Coverage gates** (separate pass, from the JSON): `python scripts/coverage_gates.py
   ../.gate/<ts>/coverage.json` — 100% on auth/authorization/tenancy/audit modules, ≥ 90% on
   `evals/*/domain`, repo-wide floor from `.coverage-floor` (never decreasing).
5. **Web**: `cd ethera-eval-web && npm ci && npm run check && npm run build`.
6. **Compose sanity**: `docker compose config -q` for the root stack with a throwaway env.
7. **Sealed files** (if any slice is sealed): `sha256sum` of every file in
   `specs/*/SEALED.md` equals the recorded hash, and `git diff <seal-commit> -- <files>` is
   empty.
8. Tear down the probe stack (`down -v`); delete leftover probes you find.

## Watchdog

Arm a monitor on the gate folder: one event per `DONE` marker, and an alarm when no test
process has been alive for 10 minutes while a log lacks its DONE marker. On a stall, read the
log yourself and continue; never wait silently.

## Output (fixed shape)

```
| Check | Result | Numbers |
| ruff format | ✓/✗ | <n> files |
| ruff check | ✓/✗ | |
| mypy | ✓/✗ | <n> source files |
| lint-imports | ✓/✗ | <kept>/<total> contracts |
| pytest | ✓/✗ | <passed> passed, <failed> failed, <skipped> skipped, <duration> |
| coverage auth/authz/tenancy/audit | ✓/✗ | <pct> (100 required) |
| coverage evals/*/domain | ✓/✗/n.a. | <pct> (≥ 90) |
| coverage repo-wide | ✓/✗ | <pct> (floor <pct>) |
| web check | ✓/✗ | <tests> tests |
| web build | ✓/✗ | |
| compose config | ✓/✗ | |
| sealed hashes | ✓/✗/n.a. | <n> files |
Logs: .gate/<ts>/
```
