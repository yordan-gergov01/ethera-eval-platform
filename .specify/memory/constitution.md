# Ethera Eval Platform Constitution

This constitution constrains the **engineering system**. It does not define what any feature
means; that is the job of the domain carriers in `docs/domain/carriers/`. Where it overlaps
with `docs/Claude_Code_Bible.md`, the Bible's wording governs.

## Core Principles

### I. Precedence (NON-NEGOTIABLE)

When two sources disagree, the higher one wins, and the place where a lower source gives way
is recorded as a dated entry in the `CLAUDE.md` decision ledger before anything is built on it:

1. The owner's explicit decisions: `docs/BRIEF.md` and every later ledger entry.
2. `docs/Claude_Code_Bible.md`, binding and followed to the letter.
3. The reference templates (template_core, template_web), as summarised in
   `docs/reference/TEMPLATE_CONVENTIONS.md`, wherever the Bible is silent.
4. The brief's defaults.

### II. The builder is never its own judge (NON-NEGOTIABLE)

- Contract-shaped work (parsers, validation, gate/comparison/recommendation rules, API and
  message contracts, the CLI) follows the sealed-oracle path: contract (WHAT, never HOW) →
  tests by a separate `test-author` agent on the strongest model → seal (hashes, local commit
  only after owner approval) → implementation that never edits a sealed file by one byte.
- UI and exploratory work follow the classic path: build → read-only lens reviews →
  adjudication → fix → gate.
- Findings, from any source including the owner's bug reports, are claims. They are verified
  against the source before a fix is written; refutations are reported with equal care.
- Artifacts, not self-reports: exit codes, logs, hashes, diffs, coverage numbers. The
  orchestrator re-runs every decisive check itself before claiming green.

### III. Template fidelity

The repository carries the templates' technology, tooling and conventions: Python 3.12,
hashed `uv pip compile` requirements, ruff, mypy strict, import-linter as a test, pytest
strict; React + Vite + strict TypeScript, TanStack Query, feature folders with ESLint
boundaries, `npm run check`. Nothing is added that the templates and the Bible do not use
without a `D-NNN` decision. No template or Bible rule is weakened to make something pass.

### IV. Module boundaries are contracts

- `ethera-eval-core/backend` is the platform core and never imports `evals`; a CI test boots
  the backend with `evals` absent.
- Domain modules live in `evals/<module>/` with `api → services → repositories → domain`;
  `domain` imports no framework, ORM, broker, HTTP or logging package.
- Modules import each other only through their barrels and only along the relationships in
  `docs/domain/context-map.md`. One feature = one module per layer (backend module ↔ web
  feature). Shared registries are append-only.
- `runner` and `demo_target` never import `backend` or `evals`; `runner` imports no ORM.
- Every boundary is enforced by import-linter or ESLint, never by convention alone.

### V. Free, local, deterministic

No paid API, no API key, no cloud service, no external call or model download at runtime.
`docker compose up -d` on a clean machine brings up the whole demo. Every model, judge,
catalog and benchmark is a seeded mock or a recorded fixture; the same scenario always
produces the same report.

### VI. One change per run

A Candidate differs from its Baseline configuration in exactly one Change. Nothing in the
system may evaluate a configuration with more than one difference.

### VII. Honest completion

A checked task is not a completed task. Done means the Bible's Phase 8 full clean gate passes
on a fresh database, re-run by the orchestrator, with numbers reported; sealed files are
unchanged (hash + empty diff); no confirmed finding is open; every shipped defect has a
`docs/FIX-REGISTRY.md` row and a mutation-checked seal. Failed and abandoned attempts stay in
the record.

### VIII. Decisions are recorded

Every owner decision, deliberate deviation and resolved conflict is a one-line, dated
`CLAUDE.md` ledger entry linking to a `D-NNN` entry in `docs/DECISIONS.md`. Assistant-introduced
requirements are **proposed policies** until the owner accepts them; specs keep open questions
open. Nothing is committed or pushed without the owner's explicit instruction in the same turn.

## Security defaults

- The template's identity and access model is kept: Argon2id, short HS256 tokens carrying no
  permissions, permissions re-read per request, endpoints check permissions never roles.
- Non-root, read-only containers with dropped capabilities, images pinned by digest, internal
  networks enforcing who talks to whom; the `sandbox` network reaches neither the database,
  the broker nor the internet.
- Secrets only from the environment; never committed, never logged. No webhook URL is ever
  committed. The never-log list of the Bible (Observability) applies in full.
- Model output and Golden content are untrusted data: rendered as plain text, never executed,
  never used as instructions.
- Audit, technical logs and metrics are three planes that never mix.

## Quality gates

- Python: `ruff format --check`, `ruff check`, `mypy`, `lint-imports`, full `pytest` on a
  freshly created database, coverage gates (100% on auth, authorization, tenancy and audit;
  ≥ 90% on `evals/*/domain`; a repo-wide floor that never decreases).
- Web: `npm run check` (Prettier, ESLint with zero warnings, `tsc -b`, Vitest) and the
  production build.
- Mechanical guards (import contracts, boot-without-`evals`, file and function length
  ratchets, docstring headers, drift guards, never-log guard, registry completeness) run as
  tests; each guard has a test proving it fires.
- Targeted green during iteration never substitutes for the final full gate.

## Governance

This constitution is amended only by an owner decision recorded in the ledger with a date and
a `D-NNN` entry; the version below is bumped (MAJOR for a removed or redefined principle,
MINOR for a new principle or section, PATCH for wording). `CLAUDE.md` points here and to
`.claude/rules/`, which hold the operational detail; a narrower container restates a rule only
to make it stricter.

**Version**: 1.0.0 | **Ratified**: 2026-10-29 | **Last Amended**: 2026-10-29
