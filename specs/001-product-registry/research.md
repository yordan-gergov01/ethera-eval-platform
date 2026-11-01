# Research: 001-product-registry (recon, Bible Phase 1)

Read-only recon on 2026-10-30, after Gate B part 1. This file holds the HOW questions that
`contract.md` must not contain: what the codebase offers, what is already decided, and the
forks for the owner at Gate B part 2. Anchors are relative to `ethera-eval-core/`.

## What the codebase has today

- **One database role.** `docker/postgres/initdb/10-create-app-role.sh:19-20` creates a
  single role that owns the database. That role:
  - runs the migrations (`backend/core/startup.py:61-66`);
  - holds the startup lock (`startup.py:37-46`);
  - serves every request (`backend/core/database.py:61-101`).
  The former test `test_application_role_owns_the_schema_without_superuser_rights`
  (`tests/integration/test_migrations.py:142-159`) pins this. The template named the split
  ("With more time", template D-001) and never built it.
- **No row security.** There is no RLS policy, no tenant setting, no `BYPASSRLS` and no
  per-request transaction. Repositories open their own `in_transaction()` blocks
  (`backend/dal/users/repository.py:221-229`). With pooled connections, a setting stays on
  one connection and clears at commit only inside such a transaction (Tortoise 1.1.8,
  `TransactionContextPooled`).
- **No module seed hook.** `ModuleMount` (`backend/core/modules.py:22-40`) has `name`,
  `router`, `models` and `migrations`, and nothing that runs at startup. The core lifespan
  must not import `evals` (`tests/integration/test_boot_without_evals.py:75-80`).
- **No service-raised field errors.** `ProblemDetails.errors: list[FieldError]` exists
  (`backend/api/errors.py:81-97`), but only request validation fills it.
- **No audit table, audit service or audit-action guard.** No Client or Client Membership.
  PyYAML is pinned for development only (`requirements/dev.txt:1422`).
- **No integration fixture boots `evals.app.create_app`.** The current `started_app` uses
  the core alone (`tests/integration/conftest.py:208-231`).

## Decided here (reversible; recorded and reported)

1. **Two database roles (D-021).** D-014 already requires a migration owner with BYPASSRLS
   and an app role without it, so this is not a fork. The work:
   - The migration owner owns the schema, runs migrations and the seed, owns the
     SECURITY DEFINER functions, and holds BYPASSRLS.
   - The runtime role gets data grants only. On the audit table that means INSERT and SELECT
     only.
   - The pinned test above changes. It now asserts the owner role owns the schema and the
     runtime role owns nothing.
   - Local database volumes need recreating once (`docker compose down -v`), because the
     init script runs only on an empty volume.
   - This supersedes template D-001's single-role rule.
2. **Module seed hook.** `ModuleMount` gains an optional `seed` callable, appended to the
   core type and run after the core's admin seed, under the startup lock. The registry seed
   reaches Clients and Memberships through the core's barrel. The core still never names a
   module.
3. **Field errors.** Manifest problems use the existing `ProblemDetails.errors` shape
   (`field`, `message`, `type`), raised by meaning from the service. There is no second error
   shape.
4. **Web feature folder `registry`.** The house rule is one feature folder per backend module
   (add-module step 6). The UI word on the page stays "Products".
5. **`eval.yaml` keys `client_id` and `project_id`.** These are the glossary's identifiers
   (the mockup showed `client` and `project`; it is updated on the web path). Refusal
   messages never quote submitted values (D-018), so the mockup's quoted values go too.
6. **Audit reads in tests come from a test fixture that reads the table directly.** No
   production audit reader is built in 001, because it would have no caller (no dead seam).

## Forks for the owner (Gate B part 2): resolved R1 = A, R2 = A (owner, 2026-10-31, D-022)

### Fork R1: how row security knows which Clients a request may see

Products lists every Client the caller is a member of, so one `app.current_tenant` value per
request (D-014's wording) cannot express it.

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | Per request, the platform reads the caller's memberships and sets the **set** of member Client IDs for the transaction. The policy is "`client_id` is in that set". | Keeps D-014's shape (tenants set per request; the policy needs no membership lookup). The setting is renamed from `app.current_tenant` to a set-valued `app.current_tenants`, which needs an amendment to `.claude/rules/database.md`, where the name appears (D-014 itself does not name it). The membership read happens before any tenant is set, so the membership table is not tenant-filtered (it is core identity data, guarded by Permissions). |
| B | The policy keys on the user: it looks up memberships of `app.current_user` inside the policy. | One setting, but every row check runs a membership subquery. Memberships become part of every policy, and an RLS bug there exposes every Client. |
| C | One tenant per request, as worded. | The list endpoint would need one query per Client with a re-set tenant. It is awkward, and it contradicts US1 as a single request. |

### Fork R2: who holds the migration owner's credentials

| Option | Means | Consequences |
|---|---|---|
| **A (recommended for the PoC)** | The backend gets both credential pairs. Under the startup lock it migrates, seeds and asserts role attributes (owner has BYPASSRLS, runtime role has NOT) on an owner connection, then serves requests on a runtime-role pool. | Matches D-014 ("asserted at startup") and keeps `docker compose up -d` unchanged. RLS still protects against application bugs. A compromised backend process could still use the owner credential. |
| B | A one-shot `migrate` service in compose holds the owner credentials. The backend has only the runtime role and starts after it completes. | Stronger isolation. It adds one service and moves the startup assertion and the seed out of the backend, which reverses the template's migrate-at-startup design (template D-004). Named as the production path either way. |

## For the plan: consequences of D-017/D-018, and choices derived by Claude (reversible)

- **Core:** new tables for Clients, Client Memberships and audit, in one core migration
  (`0004`; that number is free, D-004).
- **Permissions and errors:** two Permissions (PP-003). Derived by Claude: three new error codes (`PRODUCT_NOT_FOUND`,
  `MANIFEST_VERSION_CONFLICT`, `MANIFEST_INVALID`).
- **Audit-action guard** (derived by Claude): a completeness guard for audit actions joins
  `test_registry_completeness.py`.
- **PyYAML:** added to `requirements/backend.in`, recompiled in the order backend → runner →
  dev.
- **Registry module:** created with the `add-module` skill. That brings per-module import
  contracts, the `reg_` tables and their migration folder.
