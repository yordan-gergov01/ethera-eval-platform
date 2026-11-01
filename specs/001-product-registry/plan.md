# Plan: 001-product-registry

**Inputs:**

- `spec.md` (D-017), `contract.md` (D-022) and `research.md` (recon, R1 = A, R2 = A).
- The sealed oracle `ethera-eval-core/tests/integration/registry/` (`SEALED.md`). It never
  changes.
- D-014 (tenancy), D-018 (PyYAML), D-021 (two roles), D-023 (commits).

**How the waves run:** sequentially, one implementer agent each. A wave starts from the
previous wave's result. After the three waves come the lens reviews, adjudication, fixes and
the full gate.

## Wave 1: platform core (owner: core implementer)

**Goal:** the core offers everything the registry needs, through its barrel. No registry
code yet.

1. **Two database roles (D-021, R2 = A).**
   - *Roles.* The init script creates:
     - a migration owner (LOGIN, BYPASSRLS, owns the database and schema);
     - a runtime role (LOGIN, NOBYPASSRLS).
   - *Configuration.* `.env.example`, compose and `DatabaseSettings` gain the owner
     credential pair, together (`test_env_example.py`).
   - *Startup:* runs on an owner connection under the existing lock:
     1. assert the role attributes (owner BYPASSRLS, runtime role not) and fail fast
        otherwise;
     2. apply the migrations;
     3. run the seeds.
   - *Requests.* Served on a runtime-role pool.
   - *Grants.* Default privileges give the runtime role data access (no DDL). The audit
     table gets INSERT and SELECT only.
   - *Tests.* The test server's `fresh_database` follows the new ownership.
     `test_application_role_owns_the_schema_without_superuser_rights` is replaced by `test_migration_owner_owns_the_schema_and_the_runtime_role_owns_nothing` for two
     roles (an owner decision, D-021).
2. **Core tables in migration `0004`.**
   - `clients` (UUID PK, `client_id` slug unique, `created_at`).
   - `client_memberships` (user, client, unique pair, `created_at`).
   - `audit_rows`: actor id, action, entity type, entity id, details JSONB, client IP,
     `created_at`, append-only.
   - Core DDL only. `EXPECTED_INDEXES` is updated.
3. **Tenancy (R1 = A, D-022).** A core helper, exported through the barrel:
   - It opens a transaction.
   - Inside it, it sets `app.current_tenants` with `set_config(…, true)`, so the setting is
     cleared at commit.
   - It hands the transaction connection to a repository.
   - Member Client IDs are read from `client_memberships` for the current user. That table
     is core identity data, without RLS.
   - Policies on client-owned tables use `client_id = ANY(...)`.
   - An empty set admits no rows. An unset setting admits no rows and never errors.
4. **Audit writer.** A core service function, exported through the barrel, writes one audit
   row on a given transaction connection. Details are IDs and field names only.
   - The audit-action registry is an append-only `StrEnum` in `common_lib`.
   - A completeness guard joins `tests/architecture/test_registry_completeness.py`: every
     action is referenced.
5. **Clients and memberships.** Core service functions `ensure_client`,
   `ensure_membership` and `list_member_client_ids`, create-only and idempotent, through the
   barrel.
6. **Module seed hook.** `ModuleMount` gains an optional `seed` (async callable), run after
   the core admin seed, under the lock, on the owner connection. The core never names a
   module, and the boot-without-evals guard still holds.
7. **Barrel additions** (append-only):
   - `require_permissions`, the current-user dependency, `documented_problem`,
     `client_address`;
   - the tenancy helper;
   - the audit writer;
   - the client and membership functions.
8. **Own tests.**
   - RLS forced on every client-owned table (the check runs from wave 2, once one exists).
   - The role-attribute assertions and the startup fail-fast.
   - Tenancy: setting scope (no leak to the next pooled borrower); an empty set yields zero
     rows.
   - The audit writer: INSERT and SELECT only; UPDATE and DELETE refused for the runtime
     role.
   - 100% coverage on the tenancy and audit modules (D-008).

## Wave 2: registry module (owner: registry implementer)

1. **Module.** `add-module` for `registry`: barrel, `MODULES.py` line, import contracts
   (layers, pure domain), prefix `reg_`, migration folder.
2. **Dependency.** PyYAML runtime dependency (D-018): `requirements/backend.in`, recompiled
   backend → runner → dev.
3. **Domain.** Manifest parsing and validation exactly as contract §3.3. It is pure, with
   the per-provider full-ID rule as data. Its own tests get ≥ 90% domain coverage.
4. **Tables.** `reg_products` and `reg_manifests` (versions). Both have `client_id NOT
   NULL`, RLS ENABLE + FORCE, and policies through the wave-1 setting.
5. **Repositories.** Explicit `client_id` filters plus RLS, frozen records, and a
   tenant-isolation test per function. Version conflicts are serialised by a unique
   (`product`, `version`) constraint, with `IntegrityError` turned into a 409.
6. **Services and API.** The three endpoints of contract §2. Permissions `products:read`
   and `manifests:write` (PP-003). Error codes `PRODUCT_NOT_FOUND`,
   `MANIFEST_VERSION_CONFLICT` and `MANIFEST_INVALID`. Audit actions `manifest_created` and
   `manifest_replaced`. Log events `manifest_replaced` and `manifest_refused`.
7. **Seed.** Through the `ModuleMount.seed` hook, as contract §3.1.
8. **Test helpers.** `tests/integration/registry_fixtures.py` with exactly the contract §6
   signatures.
9. **Done when** the sealed oracle passes: 224 of 224, plus the wave's own tests.

## Wave 3: web (owner: web implementer)

1. **Feature folder.** `src/features/registry/`, plus `FEATURES` in `eslint.config.js`.
2. **Pages.** The Products list and the Product page, per the mockup (with `client_id` /
   `project_id` keys, and messages that never quote values).
3. **Replace Manifest form.** Shows `errors` by field.
4. **Label maps.** `Record<Value, Label>` maps for roles and providers (PP-011), and for
   user roles (the recon drift on the users page).
5. **API types.** Regenerated from the running backend.
6. **Tests.** Vitest for the API client and the label maps.

## After the waves

- Lenses in parallel: `security-privacy-lens`, `house-rules-lens`, `functional-spec-lens`,
  `domain-guard`.
- `adjudicator` (opus, D-011 exception).
- Fixes with `register-fix` (seal tests, no registry rows: the code is uncommitted).
- `full-gate`.
- A report to the owner. Commits only on the owner's instruction (D-023 format).
