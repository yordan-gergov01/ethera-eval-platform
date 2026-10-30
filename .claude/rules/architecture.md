# Architecture

Source: Bible Part III "Architecture — the modularity strategy", applied with brief §3 C1/C2
and §7. Modularity here is an agent-ergonomics decision first: small working sets, contained
blast radius.

## Grain

- Modular monolith. One app process (`backend`), one worker on the same codebase (`runner`),
  one public edge. The `demo_target` is not ours: it plays the client's product inside the
  `sandbox` network.
- In-process calls between our own modules. No HTTP to ourselves, no internal API keys.
  RabbitMQ is the only channel between `backend` and `runner`.

## Layout of `ethera-eval-core/`

| Package | Is | May import |
|---|---|---|
| `backend/` | Platform core: app, auth, users, roles, messaging, health, settings, errors, audit, spend | `common_lib`; never `evals`, `runner`, `demo_target` |
| `evals/<module>/` | Domain modules: `registry`, `evaluation`, `comparison`, `model_watch`, `notification` | core through its barrels, other modules through their barrels along `docs/domain/context-map.md` |
| `evals/MODULES.py` | Append-only registry of mounted modules (routers, consumers, periodic tasks) | module barrels |
| `runner/` | Worker: executes Trials, applies Metrics, publishes results | `common_lib` (ORM-free parts); never `backend`, `evals`, the ORM |
| `demo_target/` | The product under test | nothing from this repository |
| `common_lib/` | Envelope, errors, logging, schemas, ORM models of the core | nothing above it |

- **Domain imports core, never the reverse.** Core boots with `evals` absent; a test proves it.
- The composition root that mounts `evals` into the core app lives outside `backend/`
  (`evals/app.py`), so `backend` never names a domain module.

## Inside each module (C2)

`api → services → repositories → domain`, one direction only.

- `api`: thin routes (15–20 lines), permission declared on the route, no business logic.
- `services`: all use-case logic; ports as `Protocol`s; raise errors by meaning
  (`common_lib.errors`), never HTTP errors; never touch sessions or the ORM directly.
- `repositories`: all data access; return frozen records, never ORM objects; org/client
  scope filters live here.
- `domain`: entities, value objects, policies. Pure: no framework, ORM, broker, HTTP or
  logging import, no I/O, no clock reads (time is passed in).
- Each module has a barrel (`__init__.py`) exporting its public API; outsiders import the
  barrel only.

## Ports (brief §7.3)

Repositories per aggregate, `ModelCatalogSource`, `BenchmarkSource`, `SandboxLauncher`,
`EvalJobPublisher`, `NotificationChannel`, `Clock`. Fakes exist only for **external**
concerns (catalogs, benchmarks, sandbox, broker, channels, clocks). Never fake our own code
within a module.

## Shared registries (three tiers)

1. Design: shared files are **append-only** (`MODULES.py`, router mounts, permissions,
   error codes, audit actions, label maps). A feature that must EDIT existing lines of a
   registry is a smell: move the logic into the module.
2. Orchestration: in a parallel wave, each shared file has exactly one owning agent; every
   other prompt carries "do NOT touch X".
3. Insurance: every registry has an exhaustiveness guard (`Record<Value, Label>` in TS; a
   completeness test in Python).

## Database ownership

- Tables are prefixed per module: `reg_`, `eval_`, `cmp_`, `mw_`, `ntf_`. Core tables keep
  the template's names.
- A migration revision never mixes core DDL and module DDL. Each module owns its migration
  folder.
- Audit- and spend-class tables are owned by the core and written only through its service
  API.

## No dead seams

No event without a consumer, no table without a writer, no endpoint without a caller, no
stubbed adapter — all wired in the same change set or not built. A named-but-unbuilt
production adapter is recorded in `docs/DECISIONS.md`, not stubbed in code. A temporary
exception exists only as a dated ledger deviation naming the slice that closes it.

## Mechanical checks

- `tests/architecture/test_import_contracts.py` — every import-linter contract in
  `pyproject.toml` (core ↛ evals, layers per module, pure domain, runner/demo_target isolation).
- `tests/integration/test_boot_without_evals.py` — the core app starts and `/health` answers
  with `evals` unimportable.
- `tests/architecture/test_registry_completeness.py` — every Permission granted and required by
  a route; every ErrorCode referenced (no dead registry entries).
- Web: `eslint.config.js` `FEATURES` boundaries (features never import each other).
