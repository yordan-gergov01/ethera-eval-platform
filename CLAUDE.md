# Ethera Eval Platform — decision ledger

Start here: `docs/BRIEF.md` (the owner's brief) and `docs/Claude_Code_Bible.md` (binding; local
only, never committed — D-020).
Precedence: owner decisions (brief + this ledger) → Bible → templates
(`docs/reference/TEMPLATE_CONVENTIONS.md`) → brief defaults.

## Vision

Catch any change to an AI product (PR, model release/deprecation, silent model change,
dependency, knowledge, production drift, goldens/judge), run the affected product in a
sandbox with exactly ONE change, evaluate end to end against its golden Dataset, compare with
its Baseline, and tell a human what to decide — with quality, cost and latency. PoC: free,
local, deterministic mocks; `docker compose up -d` runs the demo.

## Hard rules

- **Never commit or push without the owner's explicit instruction in the same turn.**
- **Never skip a HUMAN GATE.** Genuine forks go to the owner as options with a recommendation;
  reversible decisions are made, recorded here and reported.
- Rules: `.claude/rules/` (architecture, code-quality, database, security, privacy,
  observability, testing, review, fix-registry). Decisions: `docs/DECISIONS.md`. Defects:
  `docs/FIX-REGISTRY.md`. Domain: `docs/domain/`. Constitution: `.specify/memory/constitution.md`.

## Build order

Phase A0 → A1 → **HUMAN GATE A** → slices 001-product-registry, 002-demo-target-and-dataset,
003-eval-run, 004-comparison-and-gate, 005-model-watch, 006-notifications,
007-overview-and-demo → audit mode → demo.

## Commands

- Core (`ethera-eval-core/`, venv: `uv venv --python 3.12 .venv`, then
  `uv pip install --require-hashes -r requirements/dev.txt` and `-e . --no-deps`):
  `ruff format --check . && ruff check . && mypy && lint-imports`;
  tests: `docker compose -f docker-compose.test.yml -p ethera_eval_core_test up -d --wait postgres rabbitmq`
  then `REQUIRE_INTEGRATION=1 pytest`.
- Web (`ethera-eval-web/`): `npm ci && npm run check && npm run build`.
- Full gate: the `full-gate` skill.

## Decision ledger

- 2026-10-29 — One repo, two self-contained projects (`ethera-eval-core`, `ethera-eval-web`) ([D-001](docs/DECISIONS.md#d-001-one-repository-with-two-independently-splittable-projects))
- 2026-10-29 — Precedence encoded in the constitution; Bible renamed to `Claude_Code_Bible.md` ([D-002](docs/DECISIONS.md#d-002-precedence-of-sources-the-bibles-file-name))
- 2026-10-29 — Core `backend/` + domain `evals/<module>/`; composition root `evals/app.py`; modules created per slice ([D-003](docs/DECISIONS.md#d-003-platform-core-and-domain-modules-c1-c2))
- 2026-10-29 — Prompt-job and model-switch features removed; `llm/` → `runner/`; migration 0004 deleted ([D-004](docs/DECISIONS.md#d-004-removing-the-templates-prompt-job-and-model-switch-features-llm--runner))
- 2026-10-29 — Commits/pushes only on owner instruction, seal commit included (C3) ([D-005](docs/DECISIONS.md#d-005-commits-and-pushes-only-on-the-owners-instruction-c3))
- 2026-10-30 — DEVIATION until slice 003 (owner, F-1): messaging/sweeper/long-poll machinery kept generic and unwired ([D-006](docs/DECISIONS.md#d-006-messaging-sweeper-and-long-polling-machinery-kept-generic-wired-in-slice-003))
- 2026-10-29 — One Tortoise app label + migrations package per module (spike-verified) ([D-007](docs/DECISIONS.md#d-007-one-tortoise-app-label-and-migrations-package-per-domain-module))
- 2026-10-29 — Coverage via pytest-cov; gates 100% auth/authz(/tenancy/audit), ≥90% domain, floor ([D-008](docs/DECISIONS.md#d-008-coverage-measurement-and-gates-c7))
- 2026-10-29 — Guards: headers everywhere (no exemptions), length ratchets, drift, never-log, completeness ([D-009](docs/DECISIONS.md#d-009-mechanical-guards-and-their-scope))
- 2026-10-29 — Audit and spend tables born with their first writers (001 / 003) ([D-010](docs/DECISIONS.md#d-010-audit-and-spend-tables-are-born-with-their-first-writers))
- 2026-10-29 — Spec Kit + rules/skills/agents/hooks; judges on `fable`, builders on `opus` ([D-011](docs/DECISIONS.md#d-011-agentic-setup--spec-kit-rules-skills-agents-hooks))
- 2026-10-30 — English UI; machine values via `Record<Value, Label>` maps (owner, C6) ([D-012](docs/DECISIONS.md#d-012-product-language-c6))
- 2026-10-30 — DEVIATION for the PoC: template auth kept (30-min token in `sessionStorage`) (owner, C4) ([D-013](docs/DECISIONS.md#d-013-authentication-tokens-c4--dated-deviation))
- 2026-10-30 — `client_id` tenancy, RLS ENABLE+FORCE, NOBYPASSRLS app role, staff memberships (owner, C5) ([D-014](docs/DECISIONS.md#d-014-multi-tenancy-c5))
- 2026-10-29 — Cross-vendor review only with owner CLI + consent (C8) ([D-015](docs/DECISIONS.md#d-015-cross-vendor-review-c8))
- 2026-10-29 — Production paths named, not built ([D-016](docs/DECISIONS.md#d-016-production-paths-named-not-built))
- 2026-10-30 — Slice 001 spec approved: Forks B1–B4 = A, PP-001–PP-013 accepted (Gate B part 1) ([D-017](docs/DECISIONS.md#d-017-slice-001-spec-approved--forks-b1b4-and-pp-001pp-013-gate-b-part-1))
- 2026-10-30 — PyYAML runtime dependency, `safe_load` only ([D-018](docs/DECISIONS.md#d-018-pyyaml-as-a-runtime-dependency-of-the-backend))
- 2026-10-30 — Foundation on `main`; one branch per slice; commit/push only on owner instruction in the same turn ([D-019](docs/DECISIONS.md#d-019-commits-pushes-and-branches))
- 2026-10-30 — Repository public; the Bible stays local, never committed (owner) ([D-020](docs/DECISIONS.md#d-020-public-repository-the-bible-stays-local))
- 2026-10-30 — Two DB roles: migration owner (BYPASSRLS) and runtime role; supersedes template D-001 ([D-021](docs/DECISIONS.md#d-021-two-database-roles--migration-owner-and-runtime-role))
- 2026-10-31 — Slice 001 contract approved: C-1..C-13, R1 = client-set tenancy, R2 = backend holds owner credentials (Gate B part 2) ([D-022](docs/DECISIONS.md#d-022-slice-001-contract-approved--c-1c-13-forks-r1-and-r2-gate-b-part-2))
- 2026-10-31 — EXCEPTION for slice 001 (owner): judging agents run on `opus`, Fable has no credits ([D-011](docs/DECISIONS.md#d-011-agentic-setup--spec-kit-rules-skills-agents-hooks))
- 2026-10-31 — Conventional Commits: `type(scope): summary`, scope = slice or area (owner) ([D-023](docs/DECISIONS.md#d-023-conventional-commits))
