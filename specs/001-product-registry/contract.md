# Contract: 001-product-registry

The sealed-oracle contract for the Product registry (Bible Phase 2). It states WHAT the
system must do at its public surfaces, never how.

- **Sources:** `spec.md` (approved at Gate B part 1); `docs/domain/carriers/registry.md`
  (INV-REG-01..14); `docs/domain/glossary.md`; D-014 (tenancy); D-017 (forks and policies);
  D-018 (YAML).
- **Where each rule comes from:** clauses that cite an invariant or a policy restate it.
  Clauses marked **[C-n]** are refinements chosen in this contract; they are listed in §8 for
  the owner's approval at Gate B part 2.
- **Terms** are the glossary's: Client, Client Membership, Product, Manifest, Model Binding.

## 1. Scope

**Covered (sealed):**

- The three HTTP endpoints of §2: list Products, read one Product, replace a Product's
  Manifest.
- Manifest validation as observed through the replace endpoint (§3.3).
- The startup seed of the demo Product (§3.1).
- Tenant isolation as observed through the API, on every endpoint.
- The audit rows of Manifest versions (§5), observed through a test fixture.
- Manifest content never reaching the technical logs (§5).

**Out of scope for the oracle.** Each item is covered elsewhere and is never silently
dropped:

| Item | Covered by |
|---|---|
| Earlier versions kept unchanged after a replacement (INV-REG-07). No surface reads a non-current version in slice 001. | the implementer's own tests (a database read of every version of a Product before and after) |
| The audit row written in the same transaction as its version (INV-REG-03) | the implementer's own tests (a failure injected after the audit write leaves neither row nor version) |
| Row security proven independently of the explicit filters (spec SC-002); FORCE on every client-owned table; role attributes (runtime role without BYPASSRLS, migration owner with it, asserted at startup) | the implementer's own tests, mandatory under `.claude/rules/database.md` |
| `403` on the two read endpoints. Both existing roles hold `products:read`, so no caller can reach it. | the implementer's own test that every registry route, on the full platform app, requires its declared Permission (today's `test_openapi_security.py` covers the core app only and checks authentication, not Permissions) |
| Models and migrations agree; a fresh database migrates from zero | `tests/integration/test_migrations.py` |
| The Products page and the Product page (web) | the classic path: Vitest for label maps and the API client, review against the mockup |
| Two platform instances starting at the same time on one database (one seed only). One test process cannot hold two live app instances, because the ORM state is process-global. | the implementer's own test, with two processes or two startup-lock holders |
| Log lines the platform already wrote before this slice (e.g. the seeding and login events, which carry a username) | unchanged; outside this slice |
| Creating Clients or Client Memberships through the API (PP-001, PP-002); creating Products through the API (INV-REG-14) | not built in slice 001 |

## 2. Surfaces

All paths are under `/api/v1`. Responses are JSON.

**Error bodies** are RFC 9457 problems (`content-type: application/problem+json`) with at
least `status`, `code`, `detail`, `instance` and `request_id`. Where stated, they also carry
`errors`: a list of `{field, message, type}`.

**Timestamps** are ISO 8601 with a UTC offset.

**Never asserted by the oracle:** the texts of `detail` and `errors[].message`.

**Identifiers** (PP-013):

- `client_id` and `project_id` match `^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$` **[C-1]**.
- That means 1–64 characters, made of lower-case letters, digits and `-`, with no leading or
  trailing `-`.

**Common responses on every endpoint** (existing platform behaviour):

| Condition | Status | `code` |
|---|---|---|
| no bearer token | 401 | `AUTHENTICATION_FAILED` |
| bad bearer token | 401 | `INVALID_TOKEN` |
| the caller lacks the endpoint's Permission | 403 | `PERMISSION_DENIED` |

**Permissions** (PP-003):

- `products:read` is granted to roles `admin` and `user`.
- `manifests:write` is granted to role `admin` only.
- No role bypasses Client Memberships (PP-002).

### 2.1 List Products

`GET /api/v1/products?limit=<int>&offset=<int>`. Permission: `products:read`.

**Query parameters** **[C-2]**:

- `limit`: integer 1–100, default 50.
- `offset`: integer ≥ 0, default 0.
- A value out of range → `422`, code `VALIDATION_FAILED`.

**`200` response:**

```json
{"items": [ProductSummary, ...], "total": 0, "limit": 50, "offset": 0}
```

`ProductSummary`:

```json
{
  "client_id": "acme",
  "project_id": "support-bot",
  "manifest_version": 1,
  "generation_binding": {"role": "generation", "provider": "mock", "model": "mock-gen-small-v1"},
  "changed_at": "2026-10-30T14:02:00+00:00",
  "changed_by": "admin"
}
```

- `items` holds the Products of every Client the caller is a member of, and only those.
- `items` is ordered by `client_id`, then `project_id`, ascending in byte (code point) order,
  so `a-c` sorts before `ab` **[C-2]**.
- `total` counts the same set.
- A caller with no memberships gets `200` with `items: []` and `total: 0`.
- The last four fields describe the current Manifest version:
  - `manifest_version`: its number;
  - `generation_binding`: its `generation` binding;
  - `changed_at`: when the version was created;
  - `changed_by`: the username of the user who created it.

### 2.2 Read one Product

`GET /api/v1/products/{client_id}/{project_id}`. Permission: `products:read`.

**`200` response:**

```json
{"client_id": "acme", "project_id": "support-bot", "manifest": Manifest}
```

`Manifest`:

```json
{
  "version": 1,
  "bindings": [{"role": "generation", "provider": "mock", "model": "mock-gen-small-v1"}],
  "allowed_providers": ["mock"],
  "document": "<the eval.yaml text exactly as accepted for this version>",
  "created_at": "2026-10-30T14:02:00+00:00",
  "created_by": "admin"
}
```

- `bindings` and `allowed_providers` are in document order.
- `document` is the accepted text, character for character.

**`404`, code `PRODUCT_NOT_FOUND`**, in three cases:

- no such Product;
- the caller is not a member of the Product's Client;
- a path segment does not match the identifier pattern.

The three bodies are equal except for `instance` and `request_id` (INV-REG-10).

### 2.3 Replace a Product's Manifest

`PUT /api/v1/products/{client_id}/{project_id}/manifest`. Permission: `manifests:write`.

**Request body** (JSON; unknown fields rejected):

```json
{"base_version": 1, "document": "<eval.yaml text>"}
```

- `base_version`: integer ≥ 1, required. It is the version the caller is replacing
  (INV-REG-08).
- `document`: string of 1–32,768 characters, required **[C-3]**.

**Responses**, checked in this order. The first row that applies wins.

| # | Condition | Status | `code` / body |
|---|---|---|---|
| 1 | the body is not valid JSON (existing platform behaviour: decoded before the token is checked) | 400 | `MALFORMED_REQUEST` |
| 2 | no or bad token | 401 | `AUTHENTICATION_FAILED` / `INVALID_TOKEN` |
| 3 | the caller lacks `manifests:write`, whether or not the Product exists | 403 | `PERMISSION_DENIED` |
| 4 | the body breaks the shape above | 422 | `VALIDATION_FAILED`; `errors[].field` is `body.<name>` (e.g. `body.document`) |
| 5 | the Product is missing, the caller is not a member, or a path segment does not match the identifier pattern | 404 | `PRODUCT_NOT_FOUND`, body as in §2.2 |
| 6 | `base_version` ≠ the current version number | 409 | `MANIFEST_VERSION_CONFLICT` |
| 7 | the document is not a valid Manifest (§3.3) | 422 | `MANIFEST_INVALID`, with `errors` |
| 8 | the Manifest equals the current version (§3.2) | 200 | the current `Manifest`, unchanged |
| 9 | otherwise | 201 | the new `Manifest`: `version` = current + 1, `created_by` = the caller |

## 3. Semantics

### 3.1 Products and the seed

**Products.**

- A Product is identified by (`client_id`, `project_id`).
- `project_id` is unique within its Client (INV-REG-13).
- In slice 001, Products are created only by the seed and by the test fixtures
  (INV-REG-14).

**The seed.** On start, the platform creates whatever is missing of:

- Client `acme`;
- a Client Membership of the seeded administrator (the account named by the
  `ADMIN_USERNAME` setting) in `acme`;
- Product `acme / support-bot`, with Manifest version 1. Its `document` is exactly the demo
  document below and its `created_by` is the seeded administrator. It also gets its
  `manifest_created` audit row (spec FR-002, PP-010).

**The seed never touches what already exists.**

- If Product `acme / support-bot` exists, the seed changes nothing about it, even if its
  current version is not version 1 or differs from the demo document.
- Two platform instances starting at the same time on one database create one Client, one
  Membership, one Product, one version and one audit row.

**Demo document** (version 1):

```yaml
product:
  client_id: acme
  project_id: support-bot
bindings:
  - role: generation
    provider: mock
    model: mock-gen-small-v1
allowed_providers:
  - mock
```

### 3.2 Versions (INV-REG-07, INV-REG-08)

**Numbering.**

- The versions of one Product are numbered 1, 2, 3, … with no gaps.
- An accepted replacement gets current + 1 and becomes current.

**Equality** (row 8 of §2.3) **[C-4]**:

- Two Manifests are equal when they parse to the same `product`, the same ordered list of
  `bindings` and the same ordered list of `allowed_providers`. The text is not compared.
- A document that differs from the current one only in whitespace, comments, quoting, or key
  order inside a mapping is therefore equal.
- An equal document gets `200`, with no new version and no audit row. `document` keeps the
  earlier text.

**Concurrency.** When several replacements name the same `base_version` at the same time:

- exactly one is accepted (`201`);
- every other one gets `409 MANIFEST_VERSION_CONFLICT`;
- version numbers stay gap-free;
- each accepted version has exactly one audit row.

### 3.3 Manifest validation

A document is a valid Manifest iff every rule below holds.

**Document level** (D-018):

- It is a single YAML document whose top level is a mapping.
- It uses no anchors, aliases, merge keys (`<<`) or explicit tags **[C-5]**.
- Every mapping key is a plain or quoted string scalar as typed under "Scalars" below.
  A key that is not a string (`on:`, `1:`, `2026-10-30:`, a complex `? [a]` key) is
  `unsupported_syntax` **[C-5]**.
- No mapping repeats a key **[C-5]**.
- It is nested no deeper than 10 levels **[C-5]**. The top-level mapping is level 1; each
  mapping or list nested inside a mapping or list adds one level; scalars add none.

**Scalars.**

- A plain (unquoted) scalar is typed as below (the YAML 1.1 safe-loader behaviour, D-018) **[C-6]**.
- These plain scalars are not strings:
  - booleans: `true`, `True`, `TRUE`, and the same three spellings of `false`, `yes`, `no`,
    `on` and `off`;
  - null: `~`, `null`, `Null`, `NULL`, and an empty value (`model:` with nothing after it);
  - integers: `1`, `010`, `0x1f`, `1_000`, `1:30`;
  - floats: `1.5`, `1.0e+3`, `.inf`;
  - timestamps: `2026-10-30`, `2026-10-30 10:00:00`.
- These plain scalars are strings: `tRuE`, `y`, `n` and `1e3`.
- A quoted empty value (`model: ""`) is a string. It breaks the length bound, so it is
  `invalid_value`; an unquoted empty value is null, so it is `wrong_type`.
- A quoted scalar is always a string.

**Schema** (INV-REG-12). The top level has exactly these three keys, and all are required.

| Path | Type | Rule | Source |
|---|---|---|---|
| `product` | mapping | exactly the keys `client_id` and `project_id` | INV-REG-12 |
| `product.client_id`, `product.project_id` | string | match the identifier pattern; equal the target Product's identifiers | INV-REG-13, INV-REG-09 |
| `bindings` | list of mappings | each has exactly the keys `role`, `provider` and `model` | INV-REG-12 |
| `bindings[i].role` | string | one of `generation`, `judge`, `embedding` | glossary value set |
| `bindings[i].provider` | string | a known provider; in slice 001 the only one is `mock` | INV-REG-04, PP-011 |
| `bindings[i].model` | string, 1–128 characters **[C-7]** | a full model ID for its provider | INV-REG-01, INV-REG-04 |
| `allowed_providers` | non-empty list of strings | each a known provider **[C-8]**; no duplicates **[C-8]** | INV-REG-12 |

**Roles** (INV-REG-05): exactly one `generation` binding, at most one `judge` and at most one
`embedding`.

**Allowed providers** (INV-REG-06): every `bindings[i].provider` appears in
`allowed_providers`.

**Full model ID for provider `mock`** (INV-REG-04's `mock-<family>-<size>-v<N>`, made exact)
**[C-9]**:

- The pattern is `^mock-[a-z]+-[a-z]+-v[1-9][0-9]*$`.
- Full IDs: `mock-gen-small-v1`, `mock-gen-large-v12`.
- Not full IDs: `mock-gen-small-latest`, `mock-gen-small`, `mock-gen-small-v0`,
  `mock-gen-small-v01`, `mock-gen2-small-v1`.

**Problems.**

- An invalid document yields `422 MANIFEST_INVALID`, and `errors` lists every problem as
  `{field, type, message}`.
- `field` is a path, such as `bindings[0].model`, `product.client_id`, `allowed_providers[1]`
  or a top-level key. It is `document` for `malformed` and `unsupported_syntax`.
- `errors` holds each (`field`, `type`) pair at most once.
- The order of `errors` is deterministic for a given document; the oracle compares it as a
  set.
- `message` never quotes a submitted value.

The fixed set of `type` values **[C-10]**:

| `type` | Raised when | `field` |
|---|---|---|
| `malformed` | the text is not YAML; it holds more than one document; its top level is not a mapping; or it nests deeper than 10 levels | `document` |
| `unsupported_syntax` | an anchor, alias, merge key or explicit tag appears, or a mapping key is not a string | `document` |
| `duplicate_key` | a mapping repeats a key | the path of the repeated key, e.g. `bindings[0].role` |
| `unknown_key` | a key outside the schema, at any level | the path of the key |
| `missing` | a required key is absent | the path of the key |
| `wrong_type` | a value has the wrong YAML type (§3.3 Scalars) | the path of the value |
| `invalid_value` | a value has the right type but breaks the identifier pattern, the role set, a length bound, or is an empty `allowed_providers` | the path of the value |
| `product_mismatch` | `product.client_id` or `product.project_id` differs from the target Product | that path |
| `unknown_provider` | a provider in a binding or in `allowed_providers` is not known | that path |
| `alias` | a binding's `model` is not a full model ID of its provider | `bindings[i].model` |
| `provider_not_allowed` | a binding's provider is not in `allowed_providers` | `bindings[i].provider` |
| `duplicate_role` | a second binding has the same role | `bindings[i].role`, on the second and later ones |
| `generation_required` | no binding has the role `generation` | `bindings` |
| `duplicate_value` | `allowed_providers` repeats a provider | `allowed_providers[i]`, on the second and later ones |

**Dependent problems.** One cause gives one report; independent causes are all reported
(FR-004, SC-004).

1. **Document-level problems:** `malformed`, `unsupported_syntax` and `duplicate_key`. If the
   document has one, `errors` holds exactly one problem, and no schema check follows
   **[C-11]**. When a document has several document-level defects, which one is reported is
   not contracted; the oracle seals only documents with a single document-level defect. This carves an exception out
   of SC-004 and is put to the owner in §8.
2. **`missing` and `wrong_type`:** a value that is missing or has the wrong type gets no
   further check, and neither does anything inside it.
3. **A binding's `model`:**
   - `alias` is checked only when the binding's `provider` is a known provider and `model`
     is a string of 1–128 characters.
   - An empty or overlong `model` is `invalid_value` only.
4. **`duplicate_role` and `generation_required`:**
   - They are checked only when `bindings` is a list and every binding is a mapping whose
     `role` is present, is a string and is in the role set.
   - So an empty `bindings` list yields exactly `generation_required`.
   - A role that appears k times yields `duplicate_role` on each of its 2nd to k-th
     bindings (k − 1 reports). For example, three `generation` bindings yield two.
5. **`provider_not_allowed`:** checked for every binding whose `provider` is a string,
   provided `allowed_providers` is a non-empty list of strings. That holds whether or not
   the provider is known, and whatever problems the list's elements have. A binding whose
   provider is unknown and absent from the list therefore yields `unknown_provider` and
   `provider_not_allowed` (two rules, two reports).
6. **`product_mismatch`:** checked only for identifiers that match the pattern.

### 3.4 Determinism

- Validation is a pure function of the document and the target Product.
- The same inputs give the same status, the same `errors` and the same order on every run.
- No clock, randomness or network call takes part.

## 4. Refusals

**What a refusal changes: nothing.** This holds for every refusal (400, 401, 403, 404, 409,
422) and for the `200` of an equal Manifest:

- no new version is created;
- the current version stays as it was, including its `document`;
- no audit row is written;
- the list and detail answers of every user are unchanged.

**A non-member's `404` reveals nothing.** On `GET` and on `PUT`, its status, `code` and body
equal those for a Product that does not exist, except `instance` and `request_id`.

## 5. Privacy and audit

### Audit rows

Each accepted Manifest version has exactly one audit row (INV-REG-11, PP-010).

| Field | `manifest_created` (version 1) | `manifest_replaced` (version ≥ 2) |
|---|---|---|
| `action` | `manifest_created` | `manifest_replaced` |
| `actor_id` | the `id` that `GET /api/v1/users/me` returns for the creating user (for the seed: the seeded administrator) | the caller's `id` |
| `entity_type` | `product` | `product` |
| `entity_id` | an identifier of the Product, UUID-shaped: the same on every row of one Product, different between Products | same |
| `details` | `{"product_id": <entity_id>, "client_id": "<slug>", "from_version": null, "to_version": 1, "changed_sections": []}` **[C-12]** | `{"product_id": <entity_id>, "client_id": "<slug>", "from_version": n, "to_version": n+1, "changed_sections": [<sorted top-level section names whose parsed value differs>]}` |
| `client_ip` | `null` for the seed | the caller's address |
| `created_at` | a timestamp | a timestamp |

- `details` never holds a document, a model ID, a username, an email or any other submitted
  value.
- Refusals write no audit row.

### Logs

**Events** **[C-13]**:

- Every accepted replacement (`201`) emits exactly one log line with `"event":
  "manifest_replaced"`.
- Every `MANIFEST_INVALID` refusal emits exactly one log line with `"event":
  "manifest_refused"` and an integer field `problem_count`, equal to the length of `errors`.

**What never appears.**

- No part of a submitted `document`, accepted or refused, appears in any log line.
- A unique marker string placed in a `model` value or a YAML comment never appears in the
  captured output.
- The two events above carry no username and no email.

## 6. Fixtures available

**Existing.** These are in `ethera-eval-core/tests/integration/conftest.py`:

- `fresh_database`
- `backend_settings`, whose seeded administrator has username `admin` and password
  `ADMIN_PASSWORD`
- `create_user(settings, *, username, password, role="user", is_active=True)`
- `token_for(client, username, password)`
- `bearer(token)`
- `assert_problem(response, status, code)`
- `eventually`
- `SERVER.connect_as_superuser(database)`, a method on the module-level `SERVER`

**Log capture** follows `tests/integration/test_never_log.py`: request `capsys`, build the
app inside the test after capture has started, then read `capsys.readouterr().out`, which
holds one JSON object per line.

**Provided by the implementer** in `ethera-eval-core/tests/integration/registry_fixtures.py`.
They are unsealed. The oracle may import them and rely on exactly these signatures. Every
`settings` argument is the test's `backend_settings` instance.

| Fixture or function | Behaviour |
|---|---|
| `started_platform_app` (pytest fixture; depends on `backend_settings`; yields `httpx.AsyncClient`) | the full platform app on that database, started and seeded as in §3.1; shut down at teardown |
| `platform_app(settings)` (async context manager yielding `httpx.AsyncClient`) | the same, created when entered and shut down on exit. Use it for log capture (enter after `capsys` is active) and for a second start on the same database. At most one app instance may be live in a test process: never enter it while `started_platform_app` or another `platform_app` is live, and read only through the live instance's client. |
| `async def arrange_client(settings, client_id: str) -> None` | creates a Client |
| `async def arrange_membership(settings, username: str, client_id: str) -> None` | makes an existing user a member of an existing Client |
| `async def arrange_product(settings, client_id: str, project_id: str, document: str, actor_username: str) -> None` | creates a Product with Manifest version 1 from `document` (valid for that Product) through the same path the seed uses, including its `manifest_created` audit row |
| `async def product_entity_id(settings, client_id: str, project_id: str) -> str` | the `entity_id` the Product's audit rows carry |
| `async def read_audit_rows(settings) -> list[AuditRowView]` | every audit row, in unspecified order. `AuditRowView` is a frozen record with exactly the fields of §5, `details` as a dict. The oracle compares rows as a multiset, or by `details.to_version`. |
| `def demo_document(client_id: str = "acme", project_id: str = "support-bot", model: str = "mock-gen-small-v1") -> str` | the §3.1 document, re-targeted |

**The oracle checks each helper through the API before relying on it.** For example, after
`arrange_product` and `arrange_membership`, the member's `GET` shows the Product at version 1.
A helper that writes the wrong thing then fails the oracle; it can never make an isolation
test pass vacuously.

## 7. Instruction to the test author

Enumerate the further edge cases this contract implies and seal them. List the
underdetermined cases you did NOT seal. Cover in particular the following.

**Boundaries at their own boundary:**

- identifiers of 64 and 65 characters;
- a `document` of 32,768 and 32,769 characters;
- `model` of 128 and 129 characters;
- nesting of 10 and 11 levels: only 11 yields `malformed`;
- each scalar token listed in §3.3 "Scalars";
- versions `v1`, `v0` and `v01`.

**Dependent problems:** one case per rule in §3.3 "Dependent problems", each with its exact
expected `errors` set.

**Concurrency:**

- N parallel `PUT`s on one `base_version`: one `201`, N−1 `409`s, gap-free versions, one new
  audit row.

**Refusals that consume nothing:** after each refusal class, the current version, its
`document`, the audit row count and other users' answers are unchanged.

**Tenant isolation on every endpoint**, for:

- a member of Client A only;
- an admin who is a member of Client B only;
- a user with no memberships.

A `PUT` to another Client's Product changes nothing there, as that Client's member sees it.

**The seed:**

- It is present after start.
- After a replacement to version 2 (in a first `platform_app`, then exited) and a second
  start (a second `platform_app`), the Product is still at version 2, with exactly one
  `manifest_created` row and one `manifest_replaced` row.

**Determinism:** the same invalid document gives the same `errors`, in the same order, twice.

**Logs:**

- a marker absent from the captured output;
- the events of §5 present (an anchor against a vacuous pass).

## 8. Contract-level choices for the owner (Gate B part 2)

These refine accepted rules, or fill gaps the spec left open. All were approved as written
(owner, 2026-10-31, D-022).

| ID | Choice | Alternative |
|---|---|---|
| C-1 | identifiers are 1–64 characters with no leading or trailing `-` (PP-013 states only the alphabet) | the alphabet only, with any length |
| C-2 | list paging (limit 1–100, default 50) and byte-order sorting by `client_id`, `project_id` | no paging |
| C-3 | `document` is at most 32,768 characters | another bound |
| C-4 | equality compares the parsed Manifest, so a comment-only edit is not saved | equality compares the text, so every text change makes a version |
| C-5 | anchors, aliases, merge keys, tags, non-string keys and duplicate keys are refused; depth is at most 10 | accept what a YAML 1.1 safe loader accepts |
| C-6 | plain scalars are typed as the token lists in §3.3 "Scalars" say (the YAML 1.1 safe-loader behaviour of D-018), so `no`, `on` and dates are not strings | YAML 1.2 typing |
| C-7 | `model` is 1–128 characters | another bound |
| C-8 | `allowed_providers` is non-empty, has no duplicates, and lists only known providers | allow unknown providers in that list |
| C-9 | the exact `mock` pattern: lower-case letters for family and size; `N` ≥ 1 with no leading zero | a looser pattern |
| C-10 | the fixed set of problem `type` values | — |
| C-11 | a document-level problem is reported alone, with no schema checks after it (an exception to SC-004) | report schema problems too, where the document still parses |
| C-12 | version 1's audit row has `from_version: null` and `changed_sections: []` | list every section as changed |
| C-13 | the log events `manifest_replaced` and `manifest_refused` | — |

Status: approved — owner, 2026-10-31, HUMAN GATE B part 2 (D-022): C-1 to C-13 as written.
