# Decision log — Ethera Eval Platform

Format: template_core `docs/DECISIONS.md` (Context, Options considered, Decision,
Consequences, With more time). IDs are never reused. The templates' own decisions stay in
`ethera-eval-core/docs/DECISIONS.md` and `ethera-eval-web/docs/DECISIONS.md` and are cited
here as "template_core D-0xx" / "template_web D-0xx". Each entry has a one-line, dated
pointer in the `CLAUDE.md` ledger.

Status of each decision: **owner** (in the brief or decided by the owner), **orchestrator,
reversible** (decided during the work and reported at the next gate), or **fork** (awaiting
the owner at a HUMAN GATE).

---

### D-001: One repository with two independently splittable projects

- **Context:** The brief (§2) asks for one repository, `ethera-eval-platform`, with
  `ethera-eval-core/` (laid out like template_core) and `ethera-eval-web/` (like
  template_web), each keeping its own tooling so it can become its own repository later.
- **Options considered:** A monorepo tool (workspaces, shared lint config) — less
  duplication, but couples the projects; two folders that each keep their template's full
  tooling (requirements, pyproject, pre-commit, compose / package.json, eslint, Dockerfile,
  decision log) — duplication of a few config lines, trivial split.
- **Decision (owner):** Two self-contained projects. Repository-level files are limited to
  the decision ledger (`CLAUDE.md`), `.claude/`, `.specify/`, `docs/`, `specs/`,
  `.github/workflows/`, and — in slice 007, with the demo it serves — a root
  `docker-compose.yml` that brings up the whole demo.
- **Consequences:** Each project keeps its template's README, decision log and checks. The
  templates were copied verbatim (`git archive` of template_core `e1d773d`, template_web
  `bfd286e`) and their own checks re-run green before any change (core: ruff, mypy, 7
  contracts, 506 tests; web: `npm run check`, 122 tests).
- **With more time:** Split into two repositories with a published OpenAPI contract between
  them.

### D-002: Precedence of sources; the Bible's file name

- **Context:** The brief's precedence (§0): owner decisions → the Bible → the templates →
  brief defaults. The Bible was delivered as `docs/Claude Code Bible.md`; the brief and the
  Bible's own mirror table name it `docs/Claude_Code_Bible.md`.
- **Decision (owner for precedence; orchestrator, reversible for the rename):** The
  precedence is encoded in the Spec Kit constitution (principle I). The file was renamed to
  `docs/Claude_Code_Bible.md` so every reference resolves; its content is unchanged.
- **Consequences:** Every place a lower source gives way is a dated ledger line and a D-NNN
  entry before anything is built on it.

### D-003: Platform core and domain modules (C1, C2)

- **Context:** The template is layer-first (`api/<feature>`, `services/<feature>`,
  `dal/<feature>`); the Bible is module-first (one feature = one module, barrels, blast
  radius). The brief resolves it (C1/C2).
- **Decision (owner):** `ethera-eval-core/backend/` stays the template's platform core,
  unchanged in shape. The product's domain lives in `ethera-eval-core/evals/<module>/`, each
  module `api → services → repositories → domain`, with a pure domain layer. Domain imports
  core, never the reverse; core boots without `evals` (CI test).
  **Orchestrator, reversible:** (1) the composition root that mounts the modules lives in
  `evals/app.py` and wraps `backend.main.create_app`, so `backend` never names `evals`;
  `evals/MODULES.py` is the append-only list of mounted modules. (2) No module package is
  created in A1: import-linter refuses contracts naming missing modules, and an empty module
  would be a dead seam. Each module is created by the `add-module` skill in its first slice.
- **Consequences:** The backend image's entrypoint is `evals.app:create_app`; running
  `backend.main:create_app` directly is the core-only app (used by the boot test).

### D-004: Removing the template's prompt-job and model-switch features; `llm/` → `runner/`

- **Context:** Brief A1.1: remove the prompt-job feature, keep the messaging, sweeper and
  long-polling machinery, keep identity and access; rename `llm/` to `runner/`. The
  template's `llm_settings` feature (the "current model" switch) exists only to stamp a model
  onto prompt jobs; in this platform models are chosen per Manifest (Model Bindings).
- **Options considered:** Keep `llm_settings` — a screen and endpoint with no consumer once
  prompts are gone (dead seam); remove it with prompts.
- **Decision (owner for prompts; orchestrator, reversible for `llm_settings`):** Removed: the
  prompts API, service, DAL, model, schemas, permissions (`prompts:*`), the `llm_settings`
  feature (`llm:model:*`), the runner's LLM completion providers, and their settings. The
  migration `0004_prompt_jobs_and_llm_settings` was **deleted** rather than reversed: no
  database ever applied it. Web: the `prompts` and `llm-model` features, their pages, routes
  and `FEATURES` entries. `llm/` became `runner/` (service, Dockerfile, settings
  `RunnerSettings`, broker user `runner`).
- **Consequences:** The provider Protocol + registry pattern (template `llm/providers`) comes
  back in slice 003 for Judges, built with its first caller.
- **With more time:** n/a.

### D-005: Commits and pushes only on the owner's instruction (C3)

- **Context:** The template's history is free-form; the Bible forbids committing or pushing
  without the owner's explicit instruction in the same turn.
- **Decision (owner):** Bible wins, always — including the seal commit of a sealed oracle,
  which is prepared and then requested at the gate. `.claude/settings.json` denies
  `git commit` and `git push` for agents.
- **Consequences:** Work is left uncommitted at every gate; one honest commit of the gated
  state when the owner asks.

### D-006: Messaging, sweeper and long-polling machinery kept generic, wired in slice 003

- **Context:** The brief keeps the template's messaging, sweeper and long-polling machinery
  while removing prompt jobs (owner instruction), but the machinery was typed to prompt
  payloads, and the Bible forbids dead seams. The brief names the runner's two messages
  (`EvalTrialBatchRequested`, `TrialBatchCompleted`) but their payloads are slice 003's
  contract.
- **Options considered:** (a) delete the machinery and rebuild it from the template in 003 —
  no dead code, but contradicts the owner's instruction and loses the tests; (b) keep it
  typed to prompt payloads — keeps part of the removed feature; (c) make it payload-generic,
  keep every test scenario on test-local payloads, define only the message-type names and
  queue topology now, and wire it with its first consumer in 003.
- **Decision (owner, 2026-10-30, Gate A fork F-1):** (c). Generic publisher
  (`publish(payload, queue=...)`), consumers (over a `ResultRecorder` Protocol) and runner
  worker (over a `JobHandler` Protocol); job waiter (PostgreSQL `NOTIFY`), poll-slot limiter,
  periodic tasks and heartbeat unchanged; the web long-poll loop moved to
  `src/lib/long-poll.ts` as `pollUntil<T>`. Topology: exchange `evals` (+ `evals.dlx`),
  queues `runner.jobs` and `backend.runner.results` with DLQs. The backend starts its broker
  connection (declaring the topology, so early jobs are never unroutable — template_core
  D-010); no publisher, consumer, worker handler, waiter or sweeper runs until slice 003.
- **Consequences:** A dated, bounded deviation from "no dead seams": the generic classes have
  tests but no production caller between A1 and slice 003, which closes it. The sweeper's
  action (failing stale jobs) was bound to the prompt-jobs table and returns with Eval Runs.
  Fork F-1 at Gate A: the owner accepted (c) on 2026-10-30.
- **With more time:** An outbox table for publishing (template_core D-010).

### D-007: One Tortoise app label and migrations package per domain module

- **Context:** The Bible requires per-module migration revisions that never mix core and
  domain DDL; the template uses one Tortoise app (`models`) with one `migrations` package. The
  brief asks to verify how Tortoise 1.x built-in migrations handle several apps.
- **Options considered:** One shared app and migration folder with naming conventions —
  mixed revisions possible; one app label per module with its own `migrations` package.
- **Verification (spike, 2026-10-29, Tortoise 1.1.8, PostgreSQL 18, throwaway database):**
  the config's `apps` takes one entry per module, each with its own `models` and
  `migrations` module; `MigrationLoader` builds one graph across apps; a module migration
  declares `dependencies = [("models", "0003_rate_limit_counters")]` and a
  `ForeignKeyField("models.User")` — the FK constraint to `users` was created; migrating the
  core app alone works without the module (boot-without-`evals`); a rerun applies nothing;
  the single `tortoise_migrations` table records `(app, name)`.
- **Decision (orchestrator, reversible):** Each module registers `{"models":
  ["evals.<module>.models"], "migrations": "evals.<module>.migrations"}` under app label
  `<module>` through `evals/MODULES.py`; its first migration depends on the latest core
  migration it needs. Core migrations stay in `ethera-eval-core/migrations/` (app `models`).
  The `add-module` skill encodes this.
- **Consequences:** No revision can mix core and module DDL (they are different packages).
  Cross-module FKs are allowed only along the context map. The framework is still marked
  experimental (template_core D-004); the pinned version is the mitigation.

### D-008: Coverage measurement and gates (C7)

- **Context:** The Bible requires coverage gates (100% on auth/authorization/tenancy/audit,
  a high domain floor, a repo-wide floor that never decreases); the template has no coverage
  tool.
- **Options considered:** `coverage` alone with a custom runner; `pytest-cov` (the standard
  pytest plugin, wraps `coverage`).
- **Decision (owner for the gates; orchestrator, reversible for the tool):** Add `pytest-cov`
  to `requirements/dev.in` (recompiled with hashes). The gates run as a separate pass over the
  JSON report (`scripts/coverage_gates.py`): 100% on the auth and authorization modules
  (`backend/services/auth`, `backend/core/security.py`, `backend/core/tokens.py`,
  `backend/api/dependencies/auth.py`, `backend/api/dependencies/permissions.py`,
  `common_lib/permissions.py`) — tenancy and audit modules join the list when they exist;
  ≥ 90% on `evals/*/domain` once a module exists; repo-wide floor in `.coverage-floor`,
  raised only.
- **Consequences:** One new dev-only dependency. Gaps are closed with real tests, never
  `pragma: no cover`.

### D-009: Mechanical guards and their scope

- **Context:** Bible: every rule gets a mechanical guard; brief §8.3 lists them. Template
  files predate the header rule.
- **Decision (owner for the list; orchestrator, reversible for the scope):**
  - Header guard (Role / Used by / Depends on / Key invariants): every Python file under
    `backend`, `common_lib`, `runner`, `evals`, `demo_target`, `migrations`, `scripts`,
    `tests` and every TypeScript file under `ethera-eval-web/src/` except the generated
    `schema.gen.ts`. No pinned exemptions: template files were given headers (C7 — the Bible
    wins, and §10 forbids weakening a rule to make something pass). `test_*` references in
    headers must resolve.
  - File length (cap 600) and function length (cap 100): a ratchet that pins today's
    offenders with their current size and refuses new offenders or growth.
  - import-linter as a test; boot-without-`evals`; `.env.example` ↔ compose ↔ settings drift
    (template); never-log guard over real flows; completeness tests for error codes,
    permissions and (when it exists) audit actions.
  - Every guard has a negative test proving it fires.
- **Consequences:** Guards run in the normal test suites, so the gate and CI enforce them.

### D-010: Audit and spend tables are born with their first writers

- **Context:** The brief lists audit and spend under the platform core, but the Bible's cost
  rule says the spend table is born with its first writer, and "no table without a writer"
  applies to audit as well.
- **Decision (orchestrator, reversible):** Neither table exists after A1. The audit table is
  created by the first slice that writes an audited action (001: Manifest changes); the spend
  table by slice 003 (mock model calls). Both are core-owned, INSERT + SELECT only.
- **Consequences:** The 100% coverage gate lists audit modules when they appear.

### D-011: Agentic setup — Spec Kit, rules, skills, agents, hooks

- **Context:** Brief §8.
- **Decision (owner for the content; orchestrator, reversible for formats):** Spec Kit
  `specify-cli` 1.2.6 initialised with the Claude integration and `sh` scripts (commands are
  installed as `.claude/skills/speckit-*`); a project override
  `.specify/templates/overrides/spec-template.md` adds *Domain constraints (authoritative)*,
  *Proposed policies* and *Open questions*. Nine rule files in `.claude/rules/`, eleven
  skills, eight agents. Judging roles (`test-author`, `adjudicator`) use `model: fable`
  (strongest available); builders and lenses use `opus`. Hooks: format the edited file after
  each edit; a Stop hook running fast checks on changed files, exiting 2 only on failure and
  never when `stop_hook_active` is true, so it cannot trap a session. Formats checked against
  the current Claude Code documentation (2026-10).
- **Consequences:** Project agents and skills load in new sessions.
- **Dated exception (owner, 2026-10-31):** Fable 5.1 needs usage credits the account does not
  have, so the judging roles of slice 001 (`test-author`, `adjudicator`) run on `opus`. The
  agent files keep `model: fable`; the override is passed per call and ends when credits
  exist. The seal report of slice 001 states it.

### D-012: Product language (C6)

- **Decision (owner, 2026-10-30, Gate A):** Code is English (Bible). The UI is English for this
  internal tool; enum-to-label maps are typed `Record<Value, Label>` either way, so a
  translation later is a label-map change.

### D-013: Authentication tokens (C4) — dated deviation

- **Context:** The template keeps a 30-minute bearer token in `sessionStorage` (template_web
  D-003, template_core D-006); the Bible's security rules use a short access token plus a
  rotating refresh token in an httpOnly cookie with reuse revocation.
- **Decision (owner, 2026-10-30, Gate A):** Keep the template's auth unchanged for the
  PoC, a deliberate deviation from the Bible dated 2026-10-30; upgrade path = template_core D-006 "With
  more time" (refresh tokens in httpOnly cookies, per-session revocation) together with
  template_web D-003's counterpart.

### D-014: Multi-tenancy (C5)

- **Decision (owner, 2026-10-30, Gate A):** `client_id` is the tenant key of every
  client-owned table; RLS ENABLE + FORCE with the app role NOBYPASSRLS; explicit client
  filters in repositories and JOINs; Ethera staff get explicit client memberships; the
  migration owner holds BYPASSRLS, asserted at startup. In force from slice 001, the first
  slice with client-owned tables; every data-access function gets a tenant-isolation test.

### D-015: Cross-vendor review (C8)

- **Decision (owner):** Codex/GPT review runs only if the owner provides the CLI and gives
  explicit consent per change; otherwise each report states that channel (a) was not run.
  Lens reviews and adjudication always run.

### D-016: Production paths named, not built

- **Context:** No dead seams; the PoC uses mocks and local adapters only.
- **Decision (owner):** Recorded here as the production path, with nothing stubbed in code:
  - Evaluation tooling: Langfuse (traces), DeepEval / Promptfoo / Confident AI (metrics and
    real LLM judges).
  - Sandbox adapters: a per-run container launcher, and GitHub `repository_dispatch` to run
    a product's own pipeline.
  - Observability: Ethera's internal framework (`openTelObserver(app)`,
    `openTelObserverWorker()`, `record_cost()`, `register_enricher()`, keyed by `client.id`
    and `project.id`) as the adapter for the technical-log and metrics planes.
  - No dependency on the private `ethera-framework` repository.
  - Model watching on the real web (owner, 2026-10-31): adapters behind the
    `ModelCatalogSource` and `BenchmarkSource` ports that read providers' published model
    lists, deprecation notices and prices on a schedule. The PoC uses deterministic fixture
    catalogs behind the same ports, so a real adapter replaces the fixture without touching
    the domain.

### D-017: Slice 001 spec approved — Forks B1–B4 and PP-001–PP-013 (Gate B part 1)

- **Context:** `specs/001-product-registry/spec.md` put four forks and thirteen proposed
  policies to the owner at HUMAN GATE B part 1.
- **Decision (owner, 2026-10-30, Gate B part 1):** Option A for every fork — B1: Manifests
  change through the API and a "Replace Manifest" action, validated, versioned and audited;
  B2: aliases are recognised by a per-provider full-ID rule kept as data
  (`mock-<family>-<size>-v<N>`), unknown providers refused; B3: slice 001 defines only
  `product`, `bindings` and `allowed_providers`, unknown keys refused, later slices append
  their sections; B4: Products are seeded only. PP-001 to PP-013 accepted as written in the
  spec.
- **Consequences:** The core audit table is born in slice 001 (D-010); PyYAML becomes a
  runtime dependency (D-018); Client and Client Membership enter the glossary and the core.
  The contract returns to the owner at Gate B part 2 before the oracle is written.

### D-018: PyYAML as a runtime dependency of the backend

- **Context:** Fork B1 = A accepts a pasted `eval.yaml`. PyYAML is today only a transitive
  development pin.
- **Decision (made by Claude, follows from D-017):** Add PyYAML to
  `requirements/backend.in`, recompiled with hashes in the order backend → runner → dev.
  Only PyYAML's `SafeLoader` is used: `yaml.parse` and `yaml.compose`
  with `Loader=yaml.SafeLoader` (amended 2026-10-31), so anchors, tags, key types, duplicate
  keys and depth can be seen before anything is built; nothing is ever constructed into
  Python objects. Any other loader is a defect. Parsing errors are reported by
  position, never by echoing the submitted text.
- **Consequences:** One new runtime package; the runner does not import it.

### D-019: Commits, pushes and branches

- **Context:** The owner asked to start committing and pushing (2026-10-30). C3 (D-005)
  stays: nothing is committed or pushed without the owner's instruction in the same turn, and
  `.claude/settings.json` denies `git commit` and `git push` to Claude as insurance.
- **Decision (made by Claude, reversible):** The foundation (governance, both projects, the
  slice 001 spec) lands on `main` in four commits by area. From then on each slice is
  developed on a branch named like its spec folder (`001-product-registry`) and merged into
  `main` only after the full gate passes and on the owner's instruction. Claude stages and
  prepares the commit messages. Amended (owner, 2026-10-30): the owner moved `git commit` and
  `git push` from deny to allow in `.claude/settings.json`; Claude still runs them only on the
  owner's instruction in the same turn (the CLAUDE.md hard rule is the guard now).
- **Consequences:** A root `.gitattributes` keeps LF in every checkout (the projects have
  their own). gitleaks is not yet active: `.pre-commit-config.yaml` lives in
  `ethera-eval-core/`, not at the repository root, so `pre-commit install` at the root has no
  config. Open owner call: a root config versus per-project hooks (D-001 splittability).

### D-020: Public repository; the Bible stays local

- **Decision (owner, 2026-10-30):** The GitHub repository may be public, without the Bible.
  `docs/Claude_Code_Bible.md` is gitignored and never committed; it stays binding for the
  work on the owner's machine.
- **Consequences:** References to the Bible (CLAUDE.md, the constitution, the rules, the
  brief) point to a file a fresh clone does not have; no code, test or CI job reads it. Rules
  paraphrase it by part name and never copy it wholesale.

### D-021: Two database roles — migration owner and runtime role

- **Context:** D-014 requires a migration owner holding BYPASSRLS and an app role without it.
  The template has one role that owns, migrates and serves (template D-001, "With more time:
  split the role"); recon for slice 001 confirmed it (`specs/001-product-registry/research.md`).
- **Decision (made by Claude, follows from D-014):** Split into a migration owner (owns the
  schema, runs migrations and seeds, owns SECURITY DEFINER functions, BYPASSRLS) and a
  runtime role (data grants only, NOBYPASSRLS; INSERT + SELECT on audit). Supersedes template
  D-001's single role. Who holds the owner's credentials is Fork R2 at Gate B part 2.
- **Consequences:** the pinned single-owner test is replaced by
  `test_migration_owner_owns_the_schema_and_the_runtime_role_owns_nothing`; local volumes are recreated once (`docker compose down -v`);
  `.env.example`, compose and settings gain the second credential pair together.

### D-022: Slice 001 contract approved — C-1..C-13, Forks R1 and R2 (Gate B part 2)

- **Context:** `specs/001-product-registry/contract.md` and `research.md` put thirteen
  contract-level choices and two infrastructure forks to the owner.
- **Decision (owner, 2026-10-31, Gate B part 2):** The contract is approved with C-1 to C-13
  as written, including C-11 (a document-level YAML problem is reported alone, an exception
  to SC-004). Fork R1 = A: each request's transaction carries the set of the caller's member
  Client IDs (`app.current_tenants`), and row security admits a row iff its `client_id` is
  in that set. Fork R2 = A: the backend holds both credential pairs, migrates, seeds and
  asserts role attributes on an owner connection under the startup lock, then serves on a
  runtime-role pool; a one-shot migration service is the named production path.
- **Consequences:** `.claude/rules/database.md` names `app.current_tenants`. The test-author
  writes the sealed oracle from the approved contract.

### D-023: Conventional Commits

- **Decision (owner, 2026-10-31):** Commit messages follow Conventional Commits:
  `<type>(<scope>): <summary>`, with type ∈ `feat`, `fix`, `chore`, `docs`, `test`,
  `refactor`, `ci`, `build`, `perf`. The scope is the slice number (`001`) or the area
  (`core`, `web`, `governance`). Examples: `test(001): seal the product-registry oracle`,
  `feat(001): add the Products list endpoint`, `docs(001): record the contract approval`.
  The body explains why; the `Co-Authored-By` trailer stays.
- **Consequences:** Applies from 2026-10-31. The four foundation commits already pushed to
  `main` keep their messages (rewriting pushed history is not worth it).

