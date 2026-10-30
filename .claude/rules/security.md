# Security

Source: Bible Part III "Security", template D-001/D-002/D-006/D-008/D-015, brief §3 C4.

## Identity and access (template, kept)

- Argon2id with NFKC normalisation; NIST-style length policy; a dummy hash for unknown
  usernames; identical 401 for every failed login.
- Access tokens: HS256, short-lived, carrying only user ID and token version. Every request
  re-reads the user, role and permissions from the database.
- Endpoints declare permissions, never role names
  (`dependencies=[require_permissions(Permission.X)]`). Every module enforces permissions at
  its own boundary.
- Rate limiting on every `/api/v1` request plus the login budget (template D-008).
- **C4 (owner, 2026-10-30, D-013):** the template's 30-minute token in `sessionStorage` is
  kept for the PoC — a deliberate dated deviation from the Bible's refresh-token-in-httpOnly-
  cookie rule. Upgrade path: template_core D-006 "With more time". Do not "fix" it in a slice.

## Containers and networks

- Images pinned by digest; non-root; read-only root filesystem; `cap_drop: ALL`;
  `no-new-privileges`; health checks everywhere.
- Networks: `edge` (backend's published port only), `data` (backend ↔ postgres, internal),
  `messaging` (backend ↔ rabbitmq ↔ runner, internal), `sandbox` (runner ↔ demo_target,
  internal, no route to database, broker or internet), `web` (frontend only).
- `/metrics` reachable only on internal networks.

## Secrets and supply chain

- Secrets come from the environment only; never committed, never logged, never in an image.
  `.env` files are gitignored; `.env.example` holds development placeholders only.
- No webhook URL is ever committed; `SLACK_WEBHOOK_URL` unset means the Slack channel is off.
- Python packages pinned by hash; npm exact versions with lockfile.
- gitleaks runs in pre-commit.

## Input and output

- Request schemas reject unknown fields (`extra="forbid"`); bodies limited in size.
- Uploads (if any): content-type allowlist, declared-size gate before reading, real-size gate
  after, expansion ceiling for container formats.
- Model output, Golden content and product answers are untrusted: rendered as plain text,
  never as HTML, never executed, never used as instructions to any agent.
- Trusted instructions and untrusted data are kept apart in every prompt-shaped surface.

## Mechanical checks

- `tests/unit/test_env_example.py` — `.env.example` ↔ compose ↔ settings drift.
- `tests/unit/backend/test_openapi_security.py`, `test_permissions_dependency.py` — every
  route declares its security.
- gitleaks (pre-commit); `.claude/settings.json` denies reading `.env*`.
- Coverage gate: 100% on auth and authorization modules.
