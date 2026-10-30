# Brief for Claude Code: Ethera Eval Platform — PoC/MVP

You are starting a new repository. Read this entire brief **and**
`docs/Claude_Code_Bible.md` before you do anything. Together they are the source of truth for
this project until the repository's own `CLAUDE.md` and docs take over.

---

## 0. Precedence, role and posture

### Precedence (when two sources disagree)

1. **The owner's explicit decisions** — this brief's requirements and every later decision
   recorded in `CLAUDE.md`.
2. **`docs/Claude_Code_Bible.md`** — binding, followed to the letter: its principles
   (Part I), delivery lifecycle (Part II), house rules (Part III) and orchestration mechanics
   (Part IV). This brief applies it; it never weakens it.
3. **The two reference templates** (section 2) — the concrete technology, tooling and
   conventions wherever the Bible is silent.
4. **This brief's defaults.**

Every place where a lower source must give way to a higher one is recorded as a dated entry in
the `CLAUDE.md` decision ledger, with the reason, before you build on it. Section 3 lists the
conflicts already known; you will find more.

### Role

You are the **orchestrator** in the Bible's sense: a senior engineer and domain-focused
architect who plans, delegates to subagents, and verifies their artifacts. You are not a
generic code generator. In particular:

- **The builder is never its own judge.** Acceptance tests for contract-shaped work are
  written by a separate test-author agent on the strongest model before the code exists;
  reviews are read-only and adversarial; you re-run the decisive checks yourself.
- **Trust artifacts, not self-reports** — exit codes, logs, hashes, diffs, coverage numbers.
- **Findings are claims** — including mine. Verify against the source before acting.
- **Domain-first (DDD)** — use the ubiquitous language in section 5 exactly; treat bounded
  contexts as strict boundaries; never invent aggregates, invariants or business rules.
  Genuine forks go to me as concrete options with a recommendation; reversible decisions you
  make, state and record, then proceed (asking permission for reversible work is a failure
  mode).
- **Never commit or push without my explicit instruction in the same turn** (Bible,
  Phase 9). Do the work, run the gates, leave the tree dirty, report, wait.

---

## 1. What we are building and why

**Ethera** is an AI startup that builds AI products for business clients. We need to know,
for every product we run, whether a change makes it better or worse **before** it reaches the
client. A change can be:

1. a pull request (code or prompt change);
2. a new model released by a provider;
3. a model announced for deprecation;
4. a silent change to a model we already use (an alias moves, price or latency changes);
5. a dependency change (SDK, embedding model);
6. a change to the product's knowledge (re-indexed documents);
7. degradation seen in production;
8. a change to the goldens or to the judge.

The **Ethera Eval Platform** catches such a change, finds the products it affects, runs each
affected product in an isolated sandbox with exactly **one** change applied, evaluates it end
to end against that product's golden dataset, compares the result with the product's
baseline, and tells a human what to decide, with numbers for quality, cost and latency.

### This repository is a PoC/MVP for an internal demo

Its purpose is to show the whole loop to the team, built well enough to keep developing if
they approve it. Therefore:

- **Everything is free and runs locally.** No paid APIs, no API keys, no cloud services.
  `docker compose up -d` on a clean machine brings up the whole demo.
- **All models are deterministic mocks** behind the same interfaces a real provider will use
  later. Providers, judges, model catalogs and benchmark data are mocks or recorded fixtures.
- **"Static" means no external calls**, not "no backend". The full stack from the templates
  runs locally (PostgreSQL, RabbitMQ, backend, worker, web).
- **Notifications** go to an in-app inbox and to the logs. A Slack incoming-webhook channel is
  built and tested against a fake HTTP server but stays switched off unless
  `SLACK_WEBHOOK_URL` is set; no URL is ever committed.
- **Reproducibility over realism.** Every mock is seeded; the same scenario always produces
  the same report.

### Non-goals for this PoC

- No real LLM calls and no real LLM judge. No Langfuse, DeepEval, Promptfoo or Confident AI.
  These are named in the decision log as the production path only; nothing half-built
  (Bible: no dead seams).
- No Kubernetes, no Grafana. The web app is the dashboard.
- No dependency on Ethera's private `ethera-framework` repository (section 7.7).
- No billing, no SSO.

---

## 2. Repository layout and reference templates

### Layout

One repository, `ethera-eval-platform`, with two top-level projects named after what they
are:

```
ethera-eval-platform/
  CLAUDE.md                      # the decision ledger (Bible Part V, step 2)
  .claude/                       # rules, skills, agents, settings (section 8)
  .specify/                      # Spec Kit (section 8.4)
  docs/                          # Bible, brief, domain docs, registry (section 8)
  specs/                         # one folder per slice
  ethera-eval-core/              # laid out like template_core
  ethera-eval-web/               # laid out like template_web
  .github/workflows/
```

Each project keeps its own tooling so it can be split into its own repository later. Record
this as the first ledger entry.

### Reference templates

- Backend, worker, shared library, infrastructure: https://github.com/yordan-gergov01/template_core
- Frontend: https://github.com/yordan-gergov01/template_web

They are public. Clone them into a sibling folder **outside** this repository (for example
`../_reference/`) and never commit them here.

### Conventions to carry over (Bible wins where it differs — see section 3)

**From template_core**
- Python 3.12; per-service `requirements/<service>.in` compiled with
  `uv pip compile --universal --generate-hashes` and installed with
  `pip install --require-hashes`.
- ruff (same rule set, line length 100), mypy **strict** with the pydantic plugin, pytest
  with `asyncio_mode = "auto"`, `--strict-markers`, `xfail_strict`.
- import-linter contracts in `pyproject.toml`, also run as a test.
- pre-commit with ruff, gitleaks, mypy, import-linter.
- Errors raised by meaning (`common_lib.errors`, stable `ErrorCode` values) and mapped to
  RFC 9457 problem details in one place; services never raise HTTP errors.
- structlog JSON logs; request ID through HTTP and every broker message.
- Versioned message envelope, one direct exchange, quorum queues, dead-letter queues,
  publisher confirms, at-least-once delivery with idempotent handlers, a sweeper for stuck
  jobs, long polling for results.
- A worker with **no database access and no published ports** that talks only through
  RabbitMQ, with providers behind a `Protocol` and a registry (template `llm/`).
- Tortoise ORM with built-in migrations applied at startup under an advisory lock; a
  separate non-superuser application role.
- Users, roles and permissions as in the template; endpoints check permissions, never role
  names.
- Docker: non-root, read-only filesystems, dropped capabilities, images pinned by digest,
  internal networks enforcing who talks to whom, health checks everywhere.
- `.env.example` documented line by line, with a drift test against compose and settings.
- `docs/DECISIONS.md` entries in the `D-NNN` format: Context, Options considered, Decision,
  Consequences, With more time.

**From template_web**
- React + Vite + strict TypeScript, React Router, TanStack Query for all server data, a React
  context for the session; no global store, no UI kit.
- Code organised by feature; features never import each other; pages compose features;
  ESLint enforces the boundaries (`FEATURES` list).
- API types generated from the backend's OpenAPI document.
- `npm run check` (Prettier, ESLint with zero warnings, `tsc -b`, Vitest), exact versions,
  `npm ci`.
- Runtime `/config.js`, strict CSP, no inline styles, model output rendered as plain text.
- `PROTECTED_PAGES` in `src/routes/router.tsx` drives routes, guards and navigation.

---

## 3. Known conflicts and how to resolve them

Resolve each one as stated, record it in the ledger, and raise anything not listed here as a
fork at Gate A.

| # | Conflict | Resolution |
|---|---|---|
| C1 | Template is **layer-first** (`api/<feature>`, `services/<feature>`, `dal/<feature>`); the Bible is **module-first** ("one feature = one module", barrels, blast radius) | Keep the template's `backend/` as the **platform core** unchanged in shape. Put the product's domain in a separate package of **modules** (section 7.2), each with the template's internal layers. Domain imports core, never the reverse; core boots without the domain package, proven in CI. |
| C2 | Template keeps business rules in services; the brief wants a pure domain layer | Inside each module: `api → services → repositories → domain`, enforced by import-linter. Services hold all use-case logic; domain holds entities, value objects and policies with no I/O. |
| C3 | Template commits are free-form; the Bible forbids commit/push without explicit instruction | Bible wins, always. Includes the seal commit in Phase 4: ask me for it at the gate. |
| C4 | Template auth keeps a 30-minute token in `sessionStorage`; the Bible's security rules use refresh tokens in an httpOnly cookie with rotation | **Owner fork at Gate A.** My default: keep the template's auth unchanged for the PoC and record it as a deliberate, dated deviation with the upgrade path. |
| C5 | The Bible treats multi-tenancy (RLS FORCE, NOBYPASSRLS app role, org filters) as the hardest rule; the template has no tenants | **Owner fork at Gate A.** My default: `client_id` is the tenant key for every client-owned table (Products, Datasets, Goldens, Eval Runs, spend rows); RLS ENABLE + FORCE with the template's non-superuser role as NOBYPASSRLS; Ethera staff get explicit client memberships; the migration owner holds BYPASSRLS, asserted at startup. |
| C6 | Product language | The Bible's language boundary applies: code is English. The UI is English for this internal tool unless I decide otherwise at Gate A; enum-to-label maps are typed `Record<Value, Label>` either way. |
| C7 | Template has no coverage gates, file-size ratchet, docstring headers, audit table or spend table | Bible wins: add all of them (section 8.3). |
| C8 | The Bible's cross-vendor review (Codex/GPT) may need a paid account | Run it only if I provide the CLI and give explicit consent for the change in question; otherwise record that channel (a) was not run for that change. Channel (b) and adjudication always run. |

---

## 4. Engineering rules distilled from the team's books and articles

You do not have these sources; this section is your copy of what matters. Where they overlap
with the Bible, the Bible's wording governs.

**"AI Engineering" (Chip Huyen), chapter 4**
- Evaluate each component independently **and** end to end; per turn and per task where both
  exist.
- The evaluation guideline is the most important artifact: what the product must do **and
  must not do**, the criteria, a scoring system per criterion, a rubric with examples, and a
  usefulness threshold tied to a business outcome.
- Mix methods: cheap deterministic checks on everything, expensive judges on samples.
- Slice results (by failure type, by topic) to see where a product fails and to avoid
  Simpson's paradox in aggregates.
- AI judges are inconsistent and biased; keep the judge fixed across runs you compare and
  measure its consistency.

**"System Design for the LLM Era" (Sampriti Mitra), chapter 2**
- Golden datasets (50–100 representative inputs with ideal outputs) in CI catch regressions
  from prompt changes and model upgrades; judge scores are tracked over time.
- LLM observability: cost per query, latency percentiles, provider 429/5xx, quality scores,
  escalation rate.
- An LLM gateway is the single entry point to providers: switching a model is configuration,
  not a redeploy; routing picks the cheapest model that is good enough.
- Separate trusted instructions from untrusted data; treat model output as untrusted.

**"AI-Augmented Domain-Driven Design", chapters 5 and 8**
- A rulebook has three layers: **language** (ubiquitous language, forbidden synonyms),
  **semantics** (how concepts may behave), **output structure** (fixed, comparable shapes).
- A rule lives in the broadest container that holds it: posture in `CLAUDE.md`/agents, one
  procedure in a skill, facts in files to look up. A narrower container restates a rule only
  to make it stricter.
- A **constitution** constrains the engineering system; a **domain carrier** constrains one
  feature's meaning. The spec keeps **open questions open**.
- Assistant-introduced requirements are **proposed policies** until a human accepts them.
- Traceability makes gaps visible but proves nothing: **a checked task is not a completed
  task** unless a test proves the named behavior.

**"Build Your Eval Harness" (Confident AI, part 2) — the harness to implement**
- Tag every trace with its source (`customer` vs `harness`).
- A Golden's expected output is a **decision plus the rule behind it**, with a failure type.
- One metric per failure type; each metric gets **only the evidence it needs**.
- Every Golden runs **three times** and gets a status: **always pass, always fail, flaky,
  error** (error = fewer results than trials).
- A Comparison lists per Golden: **fixed, regression, now flaky, still failing**; read from
  the bottom up, the pass rate last.
- The gate fails **only** on always pass → always fail, or on an error; flaky Goldens go to a
  human and do not block.
- When trials disagree, separate a flaky product (different answers) from a flaky judge
  (same answer, different verdicts).
- **One change per run.** Some fixes are outside the code; the report shows them with an
  owner.

**"Rethinking Software Estimation for AI-Driven Development"**
- Keep failed and abandoned attempts in the record.
- Version together the input, the data version, the AI configuration and the result.
- Recalibrate on material change, not on a calendar.

---

## 5. Domain model (DDD)

These are **starting candidates**, marked accepted (from this brief) or to be confirmed at
Gate A. Do not add to them without proposing first.

### Ubiquitous language

| Term | Meaning | Forbidden synonyms |
|---|---|---|
| **Product** | An AI application Ethera runs for a client, identified by `client_id` + `project_id` | App, Service, Bot (in code) |
| **Manifest** | The product's `eval.yaml`: model bindings, sandbox target, dataset, metrics, gate, candidate policy, allowed providers | Config, Settings |
| **Model Binding** | A role (generation, judge, embedding) bound to a provider and a **full model ID**, never an alias | Model setting |
| **Golden** | One evaluation case: input, expected outcome (decision + rule), failure type, optional context | Test case, Example |
| **Dataset** | A versioned, immutable set of Goldens for one Product | Test set |
| **Metric** | A named check for one failure type, with the evidence it receives and a threshold | Score, Grader (as a type) |
| **Judge** | The component that applies Metrics to a product output | Evaluator, Grader |
| **Eval Run** | One evaluation of one Product configuration against one Dataset version, N trials per Golden | Test run, Job (in the domain) |
| **Trial** | One execution of one Golden inside an Eval Run | Repeat, Attempt |
| **Case Result** | A Golden's status across its Trials: always pass, always fail, flaky, error | Outcome |
| **Baseline** | The accepted Eval Run a Product is compared against; immutable | Reference run |
| **Change** | Exactly one difference between a Candidate configuration and the Baseline configuration | Diff, Variant |
| **Candidate** | A Product configuration with one Change applied, evaluated in a Sandbox | Experiment |
| **Comparison** | Per-Golden transitions between two Eval Runs: fixed, regression, now flaky, still failing | Diff report |
| **Gate Verdict** | pass or fail, decided only by regressions and errors | Status, Check |
| **Recommendation** | switch, discuss or keep, from quality, cost and latency together | Suggestion |
| **Model Change** | A detected change: released, alias moved, deprecation announced, price changed, latency changed | Update |
| **Notification** | A message asking a human to decide something, linked to the evidence | Alert (except as severity) |

### Candidate modules (bounded contexts)

1. **registry** — Products, Manifests, Model Bindings, allowed providers, owners.
2. **evaluation** — Datasets, Goldens, Metrics, Eval Runs, Trials, Case Results.
3. **comparison** — Baselines, Comparisons, Gate Verdicts, Recommendations.
4. **model_watch** — catalog snapshots, Model Changes, selection of affected Products,
   scheduling of Candidate runs.
5. **notification** — Notifications, channels, weekly digest.

Identity and access stay in the platform core, unchanged from the template.

### Candidate invariants

- A Model Binding refers to a full model ID; an alias is rejected.
- A Candidate differs from its Baseline configuration in **exactly one** Change.
- A Candidate run is allowed only for providers in the Product's `allowed_providers`.
- Two Eval Runs are comparable only with the same Dataset version and judge configuration;
  otherwise the Comparison is refused with a reason.
- A Golden with fewer trial results than the run's trial count has status **error**.
- The Gate Verdict fails if and only if at least one Golden is a regression
  (always pass → always fail) or has status error.
- A Recommendation is **switch** only if the gate passes, always-pass Goldens are at least the
  Baseline's, and cost and p95 latency increases are within the Manifest's limits;
  **discuss** if quality improves but cost or latency is over its limit; otherwise **keep**,
  with the reason.
- A Baseline is immutable; promoting creates a new one and keeps the old one.
- A Notification is raised only when a human decision is needed: switch or discuss, a failed
  gate, a deprecation within 30 days. Everything else goes to the digest.
- A flaky Golden with identical trial outputs is **judge-flaky**; with different outputs,
  **product-flaky**.

### Candidate domain events

`ProductRegistered`, `ManifestChanged`, `DatasetVersionPublished`, `EvalRunRequested`,
`TrialCompleted`, `EvalRunCompleted`, `BaselinePromoted`, `ComparisonCompleted`,
`RegressionDetected`, `ModelChangeDetected`, `CandidateRunScheduled`,
`RecommendationIssued`, `NotificationRaised`.

Past tense, business facts only. **No event without a consumer in the same change set**
(Bible: no dead seams); drop any event from this list that has none.

---

## 6. The demo scenario (what must work end to end)

1. **Seeded product:** client `acme`, project `support-bot`, a fictional footwear store's
   customer-support assistant answering from a small set of help-center documents.
2. **Demo target:** a small FastAPI app (`ethera-eval-core/demo_target/`) playing this
   product inside the sandbox network. `POST /chat` returns `answer`, `retrieved_doc_ids`,
   `facts_used`, `decision` and token counts. Its instruction sets are **versioned `.md`
   files read from disk on every construction** (Bible, prompt-fix round). Behavior by
   configuration:
   - `mock-gen-small-v1` + `keyword` retrieval: wrong date math ("5 weeks" accepted against a
     30-day window); answers questions the documents do not cover.
   - `mock-gen-small-v2`: date math fixed; still misses documents keyword search cannot find.
   - `semantic` retrieval: finds the return policy for "send them back".
   - `mock-gen-medium-v1`: best quality, about 2.5× the cost per call, higher latency.
   - Each mock declares prices per 1M input/output tokens and a latency distribution. All
     randomness is seeded.
3. **Seeded dataset:** about 20 Goldens with decision + rule and failure types (date math,
   invented facts, out-of-docs, order status through a tool, refund rules), including Goldens
   that pass and one that no code change can fix (no document exists) with an owner outside
   engineering.
4. **Baseline:** an Eval Run of `mock-gen-small-v1` + `keyword`, promoted.
5. **PR scenario:** a Candidate changing only the instruction-set version → fixed and
   still-failing Goldens, zero regressions, gate passes.
6. **Retrieval scenario:** a Candidate changing only retrieval to `semantic` → the date-math
   Golden becomes always pass.
7. **Model-release scenario:** "Simulate: provider releases `mock-gen-small-v2`" advances the
   fixture clock; Model Watch detects it, selects affected Products, runs a Candidate,
   produces the Comparison and Recommendation, and raises a Notification with quality, cost
   and latency deltas and the reason.
8. **Expensive-model scenario:** `mock-gen-medium-v1` → **discuss**.
9. **Deprecation scenario:** "Simulate: deprecation of `mock-gen-small-v1` in 21 days" →
   migration Candidate run + Notification with the deadline.
10. **Judge noise:** a seeded noisy judge on one metric creates a flaky Golden, flagged
    judge-flaky, not failing the gate.
11. **CI scenario:** a GitHub Actions workflow runs the gate for the demo product on pull
    requests touching `demo_target/` or the goldens, compares with a committed baseline file,
    and fails only on regressions or errors.

Write `docs/DEMO.md`: a five-minute script for presenting this to the team. Set up the
Bible's **gitignored live-testing scenario folder** with these scenarios and a FINDINGS
journal that records emergent wins as well as defects.

---

## 7. Architecture

### 7.1 Services (modular monolith, Bible Part III)

One app process, one worker on the same codebase, one public edge. The demo target is not
ours: it plays the client's product.

| Service | Based on | Responsibility | Networks |
|---|---|---|---|
| `backend` | template_core `backend/` + the domain modules | HTTP API, all domain logic, owns the database, publishes eval jobs, consumes results, runs periodic Model Watch | edge, data, messaging |
| `runner` | template_core `llm/`, renamed | Executes Trials: calls the sandbox target, applies Metrics, publishes results. No database, no published ports | messaging, sandbox |
| `demo_target` | new, minimal FastAPI | The product under test, started with the Candidate's configuration | sandbox |
| `postgres`, `rabbitmq` | template_core | Data; the only channel between backend and runner | data; messaging |
| `web` | template_web | Dashboard and actions | its own `web` network |

The `sandbox` network is internal: runner and demo target only, no route to the database,
the broker or the internet. For the PoC the sandbox is the `demo_target` container started
with environment variables for the Candidate's model, instruction-set version and retrieval
mode, behind a `SandboxLauncher` port. Only the PoC adapter is built; the per-run container
and `repository_dispatch` adapters are named in the decision log, not stubbed.

### 7.2 Code layout inside `ethera-eval-core/`

```
ethera-eval-core/
  backend/          # PLATFORM CORE from template_core: app, auth, users, roles, messaging,
                    # health, settings, errors, audit, spend. Never imports evals/.
  evals/            # DOMAIN: one package per module, each with a barrel (__init__.py)
    registry/       #   api/ services/ repositories/ domain/ migrations/ + instruction sets
    evaluation/
    comparison/
    model_watch/
    notification/
    MODULES.py      # append-only registry of mounted modules (routers, consumers, tasks)
  runner/           # worker (template llm/), providers behind Protocols, judge, metrics
  demo_target/      # the product under test; imports nothing from this repository
  common_lib/       # template shared library (envelope, errors, logging, schemas)
  tests/            # mirrors the source tree, one test file per source file
```

Enforced by import-linter contracts that also run as a test:

- `evals` imports `backend` (core) only through core's barrels; `backend` never imports
  `evals`. **A CI test boots the backend with `evals` absent.**
- Inside each module: `api → services → repositories → domain`; `domain` imports no
  framework, ORM, broker, HTTP or logging package.
- Modules import each other only through their barrels, and only along the relationships in
  `docs/domain/context-map.md`.
- `runner` and `demo_target` never import `backend` or `evals`; `runner` imports no ORM.
- Tables are prefixed per module (`reg_`, `eval_`, `cmp_`, `mw_`, `ntf_`); a migration
  revision never mixes core and module DDL. Verify how Tortoise's built-in migrations handle
  several apps and record the mechanism.

### 7.3 Ports (Protocols) in services

At least: repositories per aggregate, `ModelCatalogSource`, `BenchmarkSource`,
`SandboxLauncher`, `EvalJobPublisher`, `NotificationChannel`, `Clock`. Fakes exist only for
**external** concerns (Bible: mock external services and clocks, never your own code within
a module). PoC adapters: Tortoise repositories, fixture-backed catalog and benchmark sources
with a fixture clock, the compose sandbox launcher, the RabbitMQ publisher, in-app and log
channels, and the Slack webhook channel (off by default).

### 7.4 Runner, judge and metrics

- Consumes a versioned `EvalTrialBatchRequested` job (template envelope), runs each Trial
  against the sandbox target, applies the Metrics, and publishes `TrialBatchCompleted` with
  per-trial output, a verdict and reason per metric, token counts, cost and latency.
- Bounded retries with backoff on target 5xx; a Trial that cannot produce a result is
  reported with an error code, never dropped.
- `Judge` is a Protocol: `RuleBasedJudge` (deterministic) and a seeded `NoisyJudge` decorator
  for the demo.
- Metrics: `policy_correct` (decision and numbers vs expected; full policy context),
  `stays_in_docs` (facts used ⊆ retrieved documents; retrieval context only),
  `answer_relevancy` (lexical), `offers_human_when_unknown`. Each declares the evidence fields
  it reads, and a test proves it reads no others.
- **Cost rule (Bible, Database):** every mock model call writes a spend row (provider, model,
  units, cost `NUMERIC`) in the same transaction as the stored Trial result. Born with its
  first writer.

### 7.5 Model Watch

- A periodic task (template `backend/core/periodic.py`) polls `ModelCatalogSource` per
  provider, diffs against the last snapshot, and emits Model Changes.
- `BenchmarkSource` gives intelligence index, price and speed per model from a recorded
  fixture shaped like a public model-benchmark API; a mapping table translates its slugs to
  provider model IDs. Pre-filter rule: skip a Candidate when the new model is worse on the
  benchmarks relevant to the Product type **and** not cheaper.
- The fixture clock advances through an admin endpoint and a "Simulate" action, protected by
  its own permission and written to the audit table.
- Each Model Change selects affected Products (same provider, same or adjacent model class,
  allowed provider) and schedules one Candidate per Product with a concurrency limit.

### 7.6 Comparison, gate, CLI and CI

- Comparison and gate logic is pure domain code, reused by the API and a CLI:
  `python -m evals.comparison.cli <baseline.json> <run.json>` prints the report (still
  failing, now flaky, regressions, fixed, then pass rates) and exits `1` only on a regression
  or an error.
- `python -m evals.evaluation.cli run --product acme/support-bot --change model=mock-gen-small-v2`
  runs a Candidate against the local stack.
- `.github/workflows/`: `core.yml` (repo-wide lint and format, full suite on a fresh
  database, coverage gates, boot-without-`evals` test), `web.yml` (`npm run check` and the
  production build), `evals.yml` (scenario 11).

### 7.7 Observability (Bible: three planes, never mixed)

- **Audit** — append-only table in the database, written in the same transaction as the
  change: manifest changes, baseline promotions, simulations, notification handling.
- **Technical logs** — stdout JSON; correlation fields (`request_id`, `user_id`,
  `eval_run_id`, `client_id`, `project_id`, `source=harness`) injected by the formatter from
  contextvars; the never-log list applies in full; route templates, never raw paths.
- **Metrics** — `/metrics` reachable only internally, labels by route template, no client
  dimension.
- Record in the ledger that Ethera's internal framework (`openTelObserver(app)`,
  `openTelObserverWorker()`, `record_cost()`, `register_enricher()`, keyed by `client.id` and
  `project.id`) is the production adapter for the technical-log and metrics planes. Build
  nothing for it now.

### 7.8 Web app (`ethera-eval-web/`)

Features mirror the backend modules one to one (Bible: one feature = one mirrored module per
layer): `products`, `eval-runs`, `comparisons`, `model-watch`, `notifications`, plus `auth`,
`profile`, `users` from the template. Pages:

- **Overview:** Products × configurations with the latest Gate Verdict and Recommendation.
- **Product:** Manifest, Model Bindings, Baseline, Eval Run history.
- **Eval Run:** Case Results per Golden with trial outputs side by side, metric verdicts and
  reasons, flaky classification, cost and latency; long polling while running.
- **Comparison:** the report in the harness order, Gate Verdict, Recommendation with its three
  axes and reason, "Promote to Baseline".
- **Model Watch:** catalog with benchmark data, Model Changes, "Simulate" actions.
- **Inbox:** Notifications linked to their evidence; mark as handled.

Every enum shown to users goes through a `Record<Value, Label>` map so a new value breaks the
build until it is labelled.

---

## 8. Agentic setup (create in Phase 1)

Check the current Claude Code documentation for the formats of memory files, rules, skills,
subagents, hooks and settings before writing them; the documentation wins over this brief on
format.

### 8.1 `CLAUDE.md` — the decision ledger

Per the Bible: vision, settled decisions **with dates**, deliberate deviations (section 3),
build order, the never-commit-or-push rule, the human-gate rule, the commands to build, test
and gate each project, and pointers to `.claude/rules/`, `docs/` and `docs/DECISIONS.md`.
Ledger lines are one line each and link to the full `D-NNN` entry; no essays. Short
`CLAUDE.md` files inside `ethera-eval-core/` and `ethera-eval-web/` hold only what differs
there.

### 8.2 `.claude/rules/` — the nine house-rule files

`architecture.md`, `code-quality.md`, `database.md`, `security.md`, `privacy.md`,
`observability.md`, `testing.md`, `review.md`, `fix-registry.md` — Bible Part III adapted to
this project and to the resolutions in section 3. Every agent prompt points at them. Every
rule that can be checked mechanically gets a test or CI gate, listed at the end of its file.

### 8.3 Mechanical guards to build in Phase 1

- import-linter contracts (section 7.2) as a test; boot-without-`evals` test.
- File-length ratchet (target 200–400 lines, hard cap 600) and function-length check (cap
  100), pinning existing offenders and refusing growth.
- Docstring header guard: every source file opens with Role / Used by / Depends on / Key
  invariants; `test_*` references in docstrings resolve to real tests.
- Coverage gates as separate CI passes: **100%** on auth, authorization, tenancy and audit
  modules; **≥ 90%** on `evals/*/domain`; a repo-wide floor; CI fails on decrease.
- Drift guards: `.env.example` ↔ compose ↔ settings (template), and frontend limits read
  from backend source where they must agree.
- Never-log guard driving real flows and asserting no forbidden fields reach the logs.
- Registry exhaustiveness: label maps typed `Record<…>`; a completeness test for backend
  registries (error codes, audit actions, permissions).

### 8.4 Spec Kit

- Install `specify-cli` with uv and initialise this repository with the Claude Code
  integration (check `specify --help` for the current command).
- The **constitution** encodes: the precedence in section 0, the Bible's principles, template
  fidelity, module boundaries and their contracts, free/local only, one change per run,
  honest completion, decisions recorded, security defaults.
- A project-local template override gives every `spec.md` the sections *Domain constraints
  (authoritative)* citing the glossary and carrier, *Proposed policies* and *Open questions*.

### 8.5 Skills (`.claude/skills/<name>/SKILL.md`)

One procedure each, with steps and a fixed output shape:

- `recon` — read-only seam map with `file:line` anchors, templates to copy by name, negative
  findings stated (Bible Phase 1).
- `write-contract` — WHAT not HOW: endpoints, shapes, status codes, invariants, edges, plus
  the instruction to enumerate implied edge cases (Bible Phase 2).
- `seal-oracle` — soundness review of the oracle, expected-failure map, SHA-256 hashes
  recorded, seal commit prepared for my approval (Bible Phases 3–4).
- `tdd-cycle` — for implementers' own additional tests: failing test, minimal code, refactor,
  checks; output shows red then green.
- `add-module` — a new domain module across all layers, its barrel, `MODULES.py` line,
  import contracts, table prefix, migration folder, mirrored web feature, glossary and carrier
  entries.
- `add-golden` — append a Golden (decision + rule, failure type), bump the Dataset version,
  never edit an existing Golden in place.
- `add-metric` — evidence fields, threshold, rubric examples, a test that fails bad cases and
  passes good ones.
- `adjudicate` — take each finding, try to refute it against the source, classify
  CONFIRMED / QUALIFIED / REFUTED with evidence, re-judge severity with the Bible's rubric.
- `register-fix` — fix + invariant-named sealing test + mutation check (revert, see red,
  restore) + `docs/FIX-REGISTRY.md` row when the defect shipped.
- `full-gate` — the Bible Phase 8 gate on a fresh probe database, logs to durable files with
  DONE markers, watchdog for stalls; outputs a table of every check with its numbers.
- `record-decision` — `D-NNN` entry plus the dated ledger line.

### 8.6 Subagents (`.claude/agents/`)

- `test-author` — **strongest available model**; receives only the contract, the test
  environment and the hard rules; touches nothing outside the test directory.
- `recon-scout` — read-only.
- Lens reviewers, read-only, one lens each, report only defects with a concrete failure
  scenario: `security-privacy-lens`, `house-rules-lens`, `functional-spec-lens` (including
  vacuous tests).
- `domain-guard` — read-only; language, ownership, invented aggregates, proposed policies.
- `adjudicator` — **strongest available model**, read-only.
- `implementer` — one tier down; every prompt carries the sealed-files prohibition verbatim.

### 8.7 Settings and hooks

- `.claude/settings.json`: allow the project's own commands (pytest, ruff, mypy,
  lint-imports, npm scripts, docker compose, read-only git); **deny** `git commit`,
  `git push` and reading `.env*` files; deny edits to sealed oracle files (paths listed per
  slice).
- Hooks: format the edited file after each edit; a pre-stop hook running the fast checks for
  what changed. The full gate runs through the `full-gate` skill, not a hook.

### 8.8 Docs

`docs/Claude_Code_Bible.md` (provided), `docs/BRIEF.md` (this file),
`docs/domain/glossary.md`, `docs/domain/context-map.md`, `docs/domain/carriers/<module>.md`,
`docs/evaluation-guideline.md`, `docs/architecture.md`, `docs/DECISIONS.md`,
`docs/FIX-REGISTRY.md` (table header and the two-artifact rule),
`docs/reference/TEMPLATE_CONVENTIONS.md`, `docs/DEMO.md`.

---

## 9. Working process (the Bible's lifecycle applied)

### Phase A0 — Read
Read the Bible and this brief in full. Clone the templates (section 2) and read both
READMEs, both decision logs, `pyproject.toml`, `.pre-commit-config.yaml`, both compose files,
`requirements/*.in`, `package.json`, `eslint.config.js`, and one complete feature in each
(backend `users`; frontend `features/users` with its page and route). Write
`docs/reference/TEMPLATE_CONVENTIONS.md` with `file:line` anchors.

### Phase A1 — Foundation
1. Scaffold `ethera-eval-core/` and `ethera-eval-web/` from the templates: rename
   identifiers, rename `llm/` to `runner/`, remove the template's prompt-job feature while
   keeping its messaging, sweeper and long-polling machinery, keep identity and access. All
   template checks pass after the move.
2. Create everything in section 8, including the mechanical guards, with tests for the
   guards themselves.
3. Write the glossary, context map, carriers and evaluation guideline from sections 5 and 6,
   marking each rule **accepted** or **proposed**.
4. Run the full gate.

**HUMAN GATE A** — report (section 9, reporting format), including forks C4, C5, C6 and any
new ones as concrete options with your recommendation. Wait.

### Phase B — Slices

Each slice follows the Bible ladder:

- **Design with the owner** (Bible Phase 0): Spec Kit specify + clarify, a visual mockup for
  any UI (an HTML artifact of the screen), forks as options. **HUMAN GATE B** per slice:
  approve the spec and, for contract-shaped work, the contract.
- **Recon** (Phase 1) by read-only scouts.
- **Path choice:** contract-shaped work (Manifest parsing and validation, the gate and
  comparison rules, the recommendation rule, API surfaces, message contracts, the CLI)
  takes the **sealed-oracle path** (Phases 2–5); UI and exploratory work take the
  **classic path** (build → lenses → adjudicate → fix → gate).
- **Plan and tasks** with Spec Kit; waves by file ownership; shared registries owned by one
  agent per wave.
- **Independent review** (Phase 6), **fixes and registry** (Phase 7), **full clean gate**
  (Phase 8). Report, then wait for my commit instruction (Phase 9).

Slices, in order:

1. `001-product-registry` — Product, Manifest schema and validation, seeded demo Product, API,
   web page.
2. `002-demo-target-and-dataset` — the demo target with seeded mocks, retrieval modes and
   versioned instruction sets; Datasets and Goldens with versioning; seed data.
3. `003-eval-run` — request a run, publish jobs, runner executes Trials, results and spend
   rows stored, Case Result statuses, run page with long polling.
4. `004-comparison-and-gate` — Baselines, Comparison, Gate Verdict, CLI, `evals.yml`.
5. `005-model-watch` — fixture sources and clock, change detection, pre-filter, Candidate
   scheduling, Recommendation.
6. `006-notifications` — inbox, log channel, Slack webhook channel (off by default), digest.
7. `007-overview-and-demo` — overview matrix, Simulate actions, `docs/DEMO.md`, the
   live-testing scenario folder, and an end-to-end test of the demo scenario against the
   Docker stack.

Before the demo, run **audit mode** once (Bible): loop-until-dry with canaries in a
disposable worktree and ceilings declared up front.

### Testing (Bible Part III, Testing)
- One test file per source file, mirrored names; `test_<function>_<scenario>_<expected>` or
  invariant-named for seals.
- For every endpoint: happy path, validation, auth (401), permission (403), not found (404)
  and, if C5 is accepted, tenant isolation.
- Golden-sample tests for every instruction set of the demo target, pinned to
  instruction-set version, schema and mock model.
- Drive the real flow through the ASGI app, the real database and broker; a test that proves
  the function but not the wiring is vacuous.
- Mock only external services and clocks; never your own code within a module, Pydantic
  validation or pure functions.
- Web: Vitest for hooks, API client, long polling, report ordering and label maps.

### Definition of done
- The Bible's Phase 8 full clean gate passes, re-run by you, numbers reported.
- Sealed files unchanged (hash and empty diff against the seal commit).
- No open confirmed findings; every shipped defect has a registry row and a mutation-checked
  seal.
- Docs, ledger, decisions and `.env.example` updated with the change.
- Tree left uncommitted unless I said otherwise in the same turn.

### Reporting format at every gate
1. Outcome first, then a table of the gate checks with numbers.
2. Files changed, grouped by module.
3. Decisions taken (ledger lines and `D-NNN` IDs) and deviations from plan with reasons.
4. Proposed policies awaiting acceptance; forks as options with a recommendation.
5. Findings: confirmed, qualified, refuted (refutations reported with the same care).
6. What happens next if I approve.

---

## 10. Things you must not do

- Call any external API or download a model at runtime.
- Commit or push without my explicit instruction in the same turn.
- Commit secrets, webhook URLs or `.env` files.
- Edit a sealed oracle file by a single byte.
- Add a library, service or pattern the templates and the Bible do not use without a
  decision.
- Weaken a template or Bible rule (security headers, import contracts, read-only containers,
  strict typing, coverage floors) to make something pass.
- Leave a dead seam: an event without a consumer, a table without a writer, an endpoint
  without a caller, a stubbed adapter.
- Mark a task done because a file or a test exists.
- Invent business rules, aggregates or metrics; propose them instead.
- Change more than one thing in a Candidate.
- Skip a HUMAN GATE.

---

## 11. First action

Do Phase A0 now, then Phase A1. Stop at HUMAN GATE A.
