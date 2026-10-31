# Database

Source: Bible Part III "Database", template D-001/D-004/D-007, brief §3 C5 and §7.2.

## Basics (in force)

- PostgreSQL via Tortoise ORM with its built-in migrations, applied at startup under an
  advisory lock. Migrations are generated, then reviewed and committed as plain files.
- UUIDv4 primary keys; `created_at` on every table; snake_case; JSONB for flexible data with
  a GIN index where queried.
- Money is `NUMERIC`, never float. Token counts are integers.
- Repositories own every query; raw SQL only with a justifying comment.
- The application connects as a non-superuser role (template D-001).
- Migrations are backward-compatible and never destructive without the owner's approval.
  Data backfills carry frozen copies of their seed constants; they never import live config.
- Table prefixes per module: `reg_`, `eval_`, `cmp_`, `mw_`, `ntf_`. A revision never mixes
  core DDL and module DDL.

## Append-only records

- **Audit** (core): who, what, when, entity, details JSONB (no personal data), client IP —
  written in the SAME transaction as the change it records. INSERT + SELECT grants only.
- **Spend** (core): every mock model call writes provider, model, units, cost `NUMERIC` in
  the same transaction as the stored Trial result. INSERT + SELECT grants only. Born with its
  first writer (slice 003), never earlier.

## Multi-tenancy (C5 — owner, 2026-10-30, D-014)

In force from slice 001, the first slice with client-owned tables:

- `client_id` is the tenant key of every client-owned table (Products, Datasets, Goldens,
  Eval Runs, spend rows); `NOT NULL`.
- RLS ENABLE **and FORCE**; the app role is `NOBYPASSRLS`; `app.current_tenants` (the set of
  the caller's member Client IDs, D-022) set per request transaction; explicit `client_id` filters in repositories too, and in JOINs.
- Ethera staff get explicit client memberships.
- The migration owner holds `BYPASSRLS`, asserted at startup; cross-tenant paths are
  `SECURITY DEFINER` functions owned by it.
- Every data-access function gets a tenant-isolation test.

## Mechanical checks

- `tests/integration/test_migrations.py` — a fresh database migrates from zero; models and
  migrations agree.
- Full suite on a freshly created probe database in the gate (`full-gate` skill).
- RLS-forced and role-attribute assertions as tests; a tenant-isolation test per repository
  function.
