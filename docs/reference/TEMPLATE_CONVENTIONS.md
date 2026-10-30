# Template conventions (Phase A0 reference)

What the two reference templates do, with `file:line` anchors, so that every agent can copy
a shape by name instead of re-reading the templates. The Bible wins wherever it differs
(brief section 3); the deviations are recorded in `docs/DECISIONS.md`.

| Template | Source | Commit read |
|---|---|---|
| template_core | https://github.com/yordan-gergov01/template_core | `e1d773d` |
| template_web | https://github.com/yordan-gergov01/template_web | `bfd286e` |

Both are cloned outside this repository at `../_reference/` and are never committed here.
Anchors below are relative to each template's root at the commit above.

---

## template_core

### Layout and responsibilities

| Path | Role |
|---|---|
| `backend/` | The only HTTP API; owns the database; applies migrations and seeds at startup (`README.md:366-372`) |
| `llm/` | asyncio worker, no ports, no database; consumes jobs, publishes results (`README.md:369`) |
| `common_lib/` | Shared: settings base, errors, logging, permissions, ORM models, schemas, message contract (`README.md:370`) |
| `migrations/` | Tortoise built-in migrations, applied at startup (`docs/DECISIONS.md` D-004) |
| `tests/` | `unit/`, `integration/`, `architecture/` |

Inside `backend/`: `api` (HTTP only) → `services` (business rules, no HTTP) → `dal` (every
query), one package per feature in each layer (`README.md:374-375`, `README.md:470-491`).

### Tooling

- Python 3.12 only: `pyproject.toml:10` (`requires-python = ">=3.12,<3.13"`), `.python-version`.
- Dependencies: per-service `requirements/<service>.in`, compiled with
  `uv pip compile --universal --generate-hashes --python-version 3.12` in the order backend →
  llm → dev (`README.md:288-295`); installed with `pip install --require-hashes`
  (`backend/Dockerfile:22-25`). `dev.in` constrains itself with `-c backend.txt -c llm.txt`
  (`requirements/dev.in:3-6`). Decision: D-014.
- ruff: rule set `pyproject.toml:29-47`, line length 100 (`pyproject.toml:26`), per-file
  ignores for migrations and tests (`pyproject.toml:49-57`).
- mypy strict + `warn_unreachable` + pydantic plugin: `pyproject.toml:62-75`.
- pytest: `--strict-markers --strict-config --import-mode=importlib`, `xfail_strict`,
  `asyncio_mode = "auto"`: `pyproject.toml:77-82`.
- import-linter contracts: `pyproject.toml:84-145`; also run as a test,
  `tests/architecture/test_import_contracts.py:32`. A contract naming a missing module fails
  (`pyproject.toml:84-85`), so contracts are added together with their modules.
- pre-commit: hygiene hooks, ruff check+format, gitleaks, then mypy and import-linter from the
  active venv (`.pre-commit-config.yaml:3-44`).

### Errors

- One closed `ErrorCode` StrEnum: `common_lib/errors.py:14`. Errors raised by meaning:
  `AppError` `:54`, `AuthenticationError` `:66`, `PermissionDeniedError` `:73`,
  `NotFoundError` `:80`, `ConflictError` `:87`, `BusinessRuleError` `:94`,
  `RateLimitExceededError` `:101`, `ServiceUnavailableError` `:122`.
- Mapped to RFC 9457 problem details in one place: `backend/api/errors.py:42`
  (`_STATUS_BY_ERROR`), handlers registered at `backend/api/errors.py:139`. Services never
  raise HTTP errors (import contract `pyproject.toml:113-118`).
- Every route documents its problems with `documented_problem` (`backend/api/errors.py:91`);
  `COMMON_ERRORS` on the `/api/v1` router (`backend/api/v1/router.py:16`).

### Logging and request ID

- structlog, JSON to stdout in containers, console locally: `common_lib/logging_config.py:87`.
  Sensitive keys redacted as a safety net: `SENSITIVE_KEYS` `:27`, `redact_sensitive` `:59`.
- Request ID: header `X-Request-ID` (`common_lib/request_id.py:6`), validated by pattern
  `:10`, set in `RequestContextMiddleware` (`backend/api/middleware.py:45`), carried in every
  message envelope (`common_lib/messaging/envelope.py:15`).
- Personal data logged by field name or length only, e.g. `backend/services/users/service.py:98`
  ("Field names only: the values are personal data").

### Messaging

- Versioned envelope `Envelope[PayloadT]`, `SCHEMA_VERSION = 1`:
  `common_lib/messaging/envelope.py:12-15`. Decision: D-003.
- One direct exchange `llm` + DLX `llm.dlx`, delivery limit 3, quorum queues:
  `common_lib/messaging/topology.py:27-31`; `QueueSpec` `:42`, `JOBS_QUEUE` `:62`,
  `RESULTS_QUEUE` `:67`.
- Payloads: `MessageType` `common_lib/messaging/jobs.py:10`, `JobPayload` `:34`,
  `JobRequested` `:44`, `JobCompleted` `:57`; closed `JobErrorCode` `:17`.
- Backend side: background connection with retry (`backend/messaging/connection.py:32`),
  declares both queues so early jobs are not unroutable (`:21-29`); publisher with confirms,
  `mandatory=True`, 5 s timeout, failure → `ServiceUnavailableError(BROKER_UNAVAILABLE)`
  (`backend/messaging/publisher.py:22-68`); consumers ack / requeue-on-DB-down / reject
  (`backend/messaging/consumers.py:1-10`, `:94-119`). Decision: D-010.
- Worker side: `JobWorker` (`llm/worker.py:62`), publishes result before acking, rejects
  rather than requeues. Heartbeat file instead of a port (`llm/heartbeat.py`).
- Broker provisioning from env into tmpfs definitions, per-service users, no guest:
  `docker/rabbitmq/provision-entrypoint.sh`; Decision D-002.

### Database

- Tortoise ORM, one app label `models` with `models: ["common_lib.models"]` and
  `migrations: "migrations"`: `backend/core/database.py:12-13`, `:30-56`. UTC everywhere
  (`:54-55`).
- Migrations applied at startup under a PostgreSQL advisory lock:
  `backend/core/startup.py:24` (`STARTUP_LOCK_ID`), `startup_lock` `:32`,
  `apply_migrations` `:55`. Decision D-004.
- `DATABASE_UNAVAILABLE_ERRORS` → 503 with `Retry-After`: `backend/core/database.py:18-27`.
- Non-superuser application role created by init script:
  `docker/postgres/initdb/10-create-app-role.sh:13-23` (role at `:19`). Decision D-001.
- Repositories return frozen dataclass records, never ORM objects
  (`backend/dal/users/repository.py:23-79`; `README.md:477-478`).
- UUIDv4 identifiers, deactivate-never-delete: D-007.

### Identity and access (kept unchanged — brief section 5)

- Permissions are a StrEnum in code, synced to DB at startup: `common_lib/permissions.py:16`;
  roles `:28`; `DEFAULT_ROLE_GRANTS` `:35`. Adding a permission: `README.md:493-497`.
- Endpoints declare permissions, never roles: `require_permissions`
  (`backend/api/dependencies/permissions.py:25`), used as
  `dependencies=[require_permissions(Permission.X)]` (`backend/api/v1/users/router.py:93`).
- HS256 JWT, 30 min, user ID + token version only; permissions re-read per request
  (`README.md:392-400`; D-006).
- Rate limiting: sliding window counter in an unlogged PostgreSQL table (D-008).

### The complete example feature: `users`

| Layer | File | What to copy |
|---|---|---|
| Schema | `common_lib/schemas/users.py:29-93` | one request schema per operation, `extra="forbid"`; `PartialUpdate` rejects null and empty PATCH (`:29-47`) |
| DAL | `backend/dal/users/repository.py` | records as frozen dataclasses (`:23-79`); `UserRepository` (`:87`); IntegrityError → domain conflict (`:105-109`); advisory-lock guarded update (`:184-222`) |
| DAL barrel | `backend/dal/users/__init__.py:3-23` | explicit re-exports + `__all__` |
| Service | `backend/services/users/service.py` | small `Protocol` for the store (`:38-58`); errors by meaning (`:212-214`); `build_user_service()` wiring (`:241-243`) |
| Route | `backend/api/v1/users/router.py` | `XServiceDep` (`:20`); documented responses (`:25-33`); thin handlers (`:90-102`) |
| Mount | `backend/api/v1/router.py:29-33`; `backend/api/dependencies/services.py:19-20` | one `include_router` + one `get_<feature>_service` |
| Tests | `tests/unit/backend/test_user_service.py` (fakes), `tests/integration/test_users_admin.py` (real DB) | unit with fakes, endpoints against the real DB |

### Application factory and background work

- `create_app(settings)`: `backend/main.py:49`; lifespan order: startup lock → migrations →
  init DB → seeding (`:84-102`), then waiter, broker, consumers, periodic tasks (`:104-121`).
- `periodic_task(name, interval_seconds, action)`: `backend/core/periodic.py:13`; failures
  logged, next run on time.
- Long polling: `JobWaiter` listens on PostgreSQL `NOTIFY job_events`
  (`backend/core/job_waiter.py`; channel `backend/core/job_events.py:7`); per-user per-replica
  cap `ConcurrentPollLimiter` (`backend/core/long_poll.py:19`). Decision D-009.
- Middleware order: `backend/main.py:155-173`.

### Docker and compose

- Multi-stage images pinned by digest, non-root uid 10001, `deps`/`runtime`/`test` stages:
  `backend/Dockerfile:9-52`; `llm/Dockerfile`.
- Compose: every service `read_only`, `tmpfs`, `cap_drop: ALL`, `no-new-privileges`, health
  checks (`docker-compose.yml:4-199`). Networks: `edge` (published), `data` and `messaging`
  internal (`docker-compose.yml:201-207`; D-015).
- Test stack as its own compose project on loopback ports 55432/55672, tmpfs data:
  `docker-compose.test.yml:1-80`. Inside Docker a missing DB fails, never skips
  (`REQUIRE_INTEGRATION`, `:73`).
- `.env.example` documented line by line; drift test against compose and settings:
  `tests/unit/test_env_example.py:52-87`.

### Tests

- Integration fixtures: `fresh_database` (`tests/integration/conftest.py:167`),
  `backend_settings` `:199`, `started_app` `:214`, `create_user` `:246`, `login`/`token_for`/
  `bearer` `:284-299`, `assert_problem` `:301`, `eventually` `:338`.
- Without the test stack, integration tests skip with instructions; with
  `REQUIRE_INTEGRATION=1` they fail (`tests/integration/conftest.py:121-141`).

### Decisions file format

`docs/DECISIONS.md` entries `### D-NNN: Title` with bullets **Context**, **Options considered**,
**Decision**, **Consequences**, **With more time** (`docs/DECISIONS.md:5-11`).

---

## template_web

### Tooling

- React 19 + Vite 8 + TypeScript 5.9 strict, exact versions, `npm ci`: `package.json:23-48`;
  Node 24 via `.nvmrc` and `engines` (`package.json:6-8`). Decision D-002.
- `npm run check` = Prettier check, ESLint `--max-warnings=0`, `tsc -b`, Vitest:
  `package.json:19`.
- TypeScript: `strict`, `noUncheckedIndexedAccess`, `erasableSyntaxOnly`, `@/*` alias:
  `tsconfig.app.json:17-27`.
- Vite dev server fixed at `localhost:3000` (CORS), serves `/config.js`: `vite.config.ts:10`,
  `:27-37`. Vitest in `node` environment for `src/**/*.test.{ts,tsx}` (`vite.config.ts:52-55`).

### Boundaries (ESLint)

- `FEATURES` list: `eslint.config.js:9`. Features never import each other or pages/routes
  (`:58-71`); shared `components`/`hooks` never import features (`:72-82`);
  `lib`/`utils`/`config`/`types` import nothing above them (`:83-99`); providers only below
  (`:100-115`). Cross-folder imports through `@/` only (`:20-23`).
- No inline `style` and no `<style>` elements (CSP): `eslint.config.js:43-56`.

### Data and session

- TanStack Query for every server read; `queryOptions` factories per feature
  (`src/features/users/api.ts:11-30`); retry rules `src/lib/query-client.ts:5-27`.
- One fetch client: `createApiClient` `src/lib/api/client.ts:39`; app instance and 401/403
  handlers `src/lib/api/http.ts:11-33`; problem-details errors `src/lib/api/errors.ts:21`,
  `apiErrorFromResponse` `:95`.
- Session in a React context: `AuthProvider` `src/providers/auth/AuthProvider.tsx:25`,
  `useAuth` `src/providers/auth/auth-context.ts:32`; `can()` by permission only
  (`src/providers/auth/permissions.ts:7`). Token in `sessionStorage`
  (`src/lib/token-storage.ts:26`, `:100`; D-003).
- API types generated from OpenAPI (`npm run api:snapshot`, `npm run api:types`,
  `package.json:12-13`); only `src/lib/api/types.ts` imports `schema.gen.ts` (D-005).
- Long polling loop with backoff and `Retry-After`: `src/features/prompts/poll-job.ts:5-47`
  (D-006).

### Routes

- `PROTECTED_PAGES` drives routes, permission guards and navigation:
  `src/routes/router.tsx:27-34`; nav derived `:36-38`; guards `:52-58`.
- `RequirePermission` (`src/routes/RequirePermission.tsx:13`), `RequireAuth`.

### The complete example feature: `users`

`src/features/users/` — `api.ts` (query options + mutations), `use-users-page.ts` (URL-kept
paging), `UsersList.tsx` (pending/error/data states, `can()` for actions), `CreateUserForm.tsx`,
`EditUserForm.tsx`, `UserDetail.tsx`; pages `src/pages/UsersPage.tsx`,
`src/pages/UserDetailPage.tsx`, `src/pages/NewUserPage.tsx` compose them; route entries
`src/routes/router.tsx:29-31`.

### Runtime config, container and CSP

- `/config.js` written at start from `BACKEND_URL` (`docker/entrypoint.d/10-runtime-config.envsh`),
  validated again in the app (`src/config/runtime-config.ts:14-43`; D-004).
- Strict CSP: `docker/nginx/templates/snippets/security-headers.conf.template:8`
  (`script-src 'self'; style-src 'self'; connect-src 'self' ${BACKEND_ORIGIN}`).
- Two-stage image, non-root nginx, digests pinned, health check on `/index.html`:
  `Dockerfile:9-35`. Compose: own `web` network only, read-only, caps dropped
  (`docker-compose.yml:8-33`).
- Model output rendered as plain text only (README "Long polling").
- Tailwind v4 via Vite plugin; no UI kit (D-007).
