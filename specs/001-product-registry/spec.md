# Feature Specification: Product registry

**Feature Branch**: `001-product-registry` (D-019)

**Created**: 2026-10-30

**Status**: Approved at HUMAN GATE B part 1 (owner, 2026-10-30, D-017): Forks B1–B4 = A,
PP-001–PP-013 accepted. The contract returns at Gate B part 2.

**Input**: Brief §9 slice 1: "`001-product-registry` — Product, Manifest schema and
validation, seeded demo Product, API, web page." Brief §7.8: "Product: Manifest, Model
Bindings, Baseline, Eval Run history."

## Domain constraints (authoritative) *(mandatory)*

- **Bounded context(s)**: `registry` (new module, prefix `reg_`); the platform core for
  audit (`docs/domain/context-map.md`, core row) and — if PP-001/PP-002 are accepted —
  Clients and Client Memberships (the core row of the context map and the glossary are then
  updated). No other domain module is touched.
- **Glossary terms used**: Product, Manifest, Model Binding (docs/domain/glossary.md). Value
  set: Model Binding role ∈ {`generation`, `judge`, `embedding`}. "Client" is not yet a
  glossary term — see PP-001.
- **Accepted invariants that apply** (docs/domain/carriers/registry.md):
  - INV-REG-01: A Model Binding refers to a full model ID; an alias is rejected.
  - INV-REG-03: A Manifest change writes an audit row in the same transaction (applies only
    if this slice has a Manifest-change path — Fork B1).
  - INV-REG-02 (allowed providers) is owned here as data; it is *enforced* where Candidates
    are scheduled (slice 005), not in this slice.
  - Product is identified by `client_id` + `project_id`; demo seed client `acme`, project
    `support-bot` (brief §6.1).
- **Tenancy (owner, 2026-10-30, D-014)**: `client_id` NOT NULL on every client-owned table;
  RLS ENABLE + FORCE; the app role NOBYPASSRLS; explicit client filters in repositories and
  JOINs; Ethera staff get explicit client memberships; the migration owner
  holds BYPASSRLS, asserted at startup; every endpoint and every data-access function has a
  tenant-isolation test.
- **Language (owner, 2026-10-30, D-012)**: English UI; every machine value shown to users
  through a `Record<Value, Label>` map.
- **Domain events produced / consumed**: **none.** `ProductRegistered` has no consumer;
  `ManifestChanged`'s candidate consumer is model_watch (slice 005), so it is born there.

## User Scenarios & Testing *(mandatory)*

Actors: **Ethera staff** — users with template role `user` or `admin`, with explicit client
memberships (D-014; whether any role bypasses them is PP-002). Only `admin` may replace a
Manifest (PP-003).

### User Story 1 — See the Products I look after (Priority: P1)

A staff member signs in and opens Products. They see every Product of every client they are
a member of — client, project, generation model — and nothing of any other client.

**Why this priority**: Every later slice (Eval Runs, Comparisons, Model Watch) starts from a
Product; tenancy is the hardest rule and lands here first.

**Independent Test**: Seed two clients with one Product each; a member of one client lists
Products and sees exactly one.

**Acceptance Scenarios**:

1. **Given** the demo seed and the seeded administrator as a member of `acme`, **When** they
   open Products, **Then** they see `acme / support-bot`.
2. **Given** a user with no membership, **When** they open Products, **Then** the list is
   empty (not an error).
3. **Given** a member of client A only, **When** they request a Product of client B by its
   identifier, **Then** the answer is indistinguishable from a Product that does not exist
   (PP-004).

### User Story 2 — Read a Product's Manifest and Model Bindings (Priority: P1)

A staff member opens a Product and sees its current Manifest: the Model Bindings (role,
provider, full model ID) and the allowed providers, with when and by whom it was last
changed (and its version number, PP-007).

**Why this priority**: The Product page is the slice's visible outcome and the anchor for the
demo story ("this product runs on `mock-gen-small-v1`").

**Independent Test**: Open `acme / support-bot`; the bindings shown equal the seeded
Manifest.

**Acceptance Scenarios**:

1. **Given** the demo seed, **When** a member opens `acme / support-bot`, **Then** the page
   shows a `generation` binding to provider `mock`, model `mock-gen-small-v1`, and `mock` in
   allowed providers.
2. **Given** the page, **Then** every role and provider is shown through its label map; an
   unlabelled value fails the web build.

### User Story 3 — Replace a Product's Manifest, with validation (Priority: P2 — only if Fork B1 = A)

An administrator who is a member of the client pastes a new `eval.yaml` for the Product. A
valid Manifest becomes the current one (kept as a new version, PP-007); an invalid one is refused with every problem
listed by field, and nothing changes.

**Why this priority**: It gives INV-REG-01 and INV-REG-03 a real path, and it is how the
demo shows an alias being refused.

**Independent Test**: Submit a Manifest binding `mock-gen-small-latest`; it is refused with
the field path and reason; the current version is unchanged and no audit row is written.

**Acceptance Scenarios**:

1. **Given** version 1 is current, **When** an admin member submits a valid Manifest that
   changes the generation model, **Then** version 2 becomes current, version 1 is kept
   (PP-007), and one audit row records who, when, which Product and versions 1 → 2 (IDs and field names
   only, never content).
2. **Given** a Manifest whose binding uses an alias, **When** submitted, **Then** it is
   refused with the binding's path and the reason "alias, not a full model ID"; nothing
   is stored, no audit row.
3. **Given** a Manifest with an unknown key, a missing required section, an unknown role,
   or a malformed document, **When** submitted, **Then** it is refused with each problem
   listed; nothing is stored.
4. **Given** a staff member without the write permission, **When** they submit, **Then**
   they are refused (403) and nothing changes.
5. **Given** an admin who is not a member of the Product's client, **When** they submit,
   **Then** the answer equals "Product not found" (PP-004).
6. **Given** a Manifest whose `product` identity differs from the target Product, **When**
   submitted, **Then** it is refused (PP-012).

### Edge Cases

- A Manifest identical to the current one (PP-007).
- Two replacements of the same Product at the same time: exactly one wins per version
  number; the loser gets a conflict, never a silent overwrite (PP-008).
- A very large or deeply nested document: refused by size before parsing (security rules,
  input).
- YAML features that execute or reference (tags, anchors to arbitrary objects): never
  honoured — only plain mappings, lists, strings, numbers, booleans.
- Two bindings with the same role (PP-005).
- A binding whose provider is not in allowed providers (PP-006).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST hold Products, each identified by `client_id` + `project_id`
  (the identifiers' shape is PP-013).
- **FR-002**: The system MUST seed the demo Product `acme / support-bot` with a valid
  Manifest binding `generation` to `mock` / `mock-gen-small-v1`, idempotently (re-running the
  seed changes nothing).
- **FR-003**: Users MUST see only Products of clients they are members of — in lists, in
  detail, and in every write — enforced both by explicit filters and by the database's row
  security.
- **FR-004**: The system MUST validate a Manifest against its schema (Fork B3) and against
  INV-REG-01, reporting every problem with its field path, never just the first.
- **FR-005** *(Fork B1 = A)*: An authorised member MUST be able to replace a Product's
  Manifest; each accepted replacement writes one audit row in the same transaction
  (INV-REG-03) and is kept as a new immutable version (PP-007).
- **FR-006**: The Product page MUST show the current Manifest's Model Bindings, allowed
  providers, last change (when, by whom) and version number (PP-007).
- **FR-007**: Every endpoint MUST declare its Permission; the Permissions are PP-003.
- **FR-008**: Nothing a user submits as Manifest content is logged; audit details hold IDs,
  version numbers and field names only.

### Key Entities

- **Client** *(PP-001)*: the Ethera customer that owns Products; the tenant key.
- **Client Membership** *(PP-002)*: grants one user access to one client's data.
- **Product**: `client_id` + `project_id`; has a current Manifest.
- **Manifest** (versioned, PP-007): an immutable, numbered Manifest of one Product: its
  Model Bindings and allowed providers (Fork B3), plus who created it and when.
- **Model Binding**: role, provider, full model ID; part of a Manifest.
- **Audit row** (core-owned plane, D-010, `.claude/rules/database.md`) *(Fork B1 = A)*:
  actor, action, entity, details (IDs and field names), client IP, time — append-only. Not
  a domain term; its action value is PP-010.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every endpoint of the slice, 0 cross-client reads or writes in the
  tenant-isolation tests (and, if PP-004 is accepted, a non-member gets the same answer as
  for a non-existent Product).
- **SC-002**: With the explicit filter removed from a repository function, its
  tenant-isolation test still passes because row security refuses the rows (RLS proven
  independently of the filter), and vice versa.
- **SC-003**: 100% of the seeded Manifest's fields appear on the Product page.
- **SC-004**: An invalid Manifest with N independent problems yields N reported problems.
- **SC-005**: Every rejected or accepted replacement leaves exactly 0 or 1 audit rows
  respectively (each Manifest version has exactly one audit row, PP-010).

## Forks for the owner (HUMAN GATE B)

Each fork is a genuine choice with consequences; my recommendation comes first.
**Resolved (owner, 2026-10-30, D-017): option A for B1, B2, B3 and B4.**

### Fork B1 — How is a Manifest changed? (OQ-REG-02)

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | API + Product page action "Replace Manifest" (paste `eval.yaml`), validated, versioned, audited. The seed loads the demo `eval.yaml` through the same service. | Adds the runtime dependency PyYAML (`safe_load` only, D-NNN, recompile backend → runner → dev); the core audit table is born here (D-010); a write Permission. Demo can show an alias refused. |
| B | Read-only in 001: the seed writes the Manifest; no write endpoint. | No YAML dependency if the seed is Python data; no audit table yet; INV-REG-01 is validated only on the seed path and INV-REG-03 has no writer until a later slice. |
| C | Loaded from `eval.yaml` files in the repository at startup, no API. | Two sources of truth once Model Watch proposes changes; files outside tenancy. |

### Fork B2 — How is an alias recognised? (OQ-REG-01)

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | A per-provider full-ID rule kept as data in `registry` — for provider `mock`: `mock-<family>-<size>-v<N>` (e.g. `mock-gen-small-v1`); anything else (e.g. `mock-gen-small-latest`) is an alias. An unknown provider is refused. | Works in 001 with no catalog. In slice 005 the catalog (which already knows aliases, "alias moved" is a Model Change kind) may add a second check — a separate owner decision then. |
| B | Look the ID up in the model catalog fixture. | Pulls the catalog (slice 005, model_watch) into 001 and reverses the context-map edge model_watch → registry. |

### Fork B3 — How much of the Manifest does 001 define?

The brief lists sandbox target, Dataset, Metrics, gate, candidate policy and cost/latency
limits; none of their inner shapes exists yet.

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | 001 defines `product` (client, project), `bindings` and `allowed_providers` only; unknown keys are refused. Each later slice appends its section with its consumer (002: Dataset, sandbox target; 003: Metrics, trials; 004: gate; 005: candidate policy, limits). | No invented shapes, no opaque data; the demo `eval.yaml` grows per slice. |
| B | Define every section now. | Invents gate, Metric and policy shapes before their slices — exactly what the brief forbids. |
| C | Accept later sections as unvalidated opaque blobs. | Stores unchecked data; violates "reject unknown fields". |

### Fork B4 — Product creation

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | Seed only in 001 (`acme / support-bot`); tests create their own clients and Products. | Smallest slice; the demo needs one Product. |
| B | "Register Product" form + endpoint for admins. | More surface; also needs a Client management path. |

## Proposed policies *(mandatory; may be "none")*

- **PP-001**: Add the glossary term **Client** — "an Ethera customer that owns Products; the
  tenant key" — code form `Client`; forbidden synonyms Customer, Org (in code). "Tenant" stays
  reserved for the isolation mechanism (`app.current_tenant`, tenant-isolation tests), recorded
  as a pair in the glossary. A core-owned table (`clients`: id, name; identifier shape
  PP-013). Seed: `acme`. — Why: D-014 needs a tenant
  key with integrity, and the brief names `client_id`. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-002**: **Client Membership** is core-owned (identity and access, 100% coverage gate):
  one row per (user, client); no role bypasses it, administrators included. Seed: the seeded
  administrator is a member of `acme`. Memberships are seeded only in 001 (no management
  UI). — Why: D-014 "explicit memberships"; tenancy is a core concern. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-003**: Permissions `products:read` (granted to `admin` and `user`) and
  `manifests:write` (granted to `admin` only, Fork B1 = A). — Why: endpoints declare
  Permissions; the completeness guard demands both a grant and a route. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-004**: A Product of a client the caller is not a member of answers **404**, never 403
  — Why: a 403 confirms the Product exists. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-005**: A Manifest has exactly one `generation` binding, at most one `judge` and at
  most one `embedding`. — Why: the demo varies one generation model per Candidate. — Status:
  accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-006**: Every binding's provider must be in the Manifest's `allowed_providers`. — Why:
  a Product bound to a disallowed provider contradicts INV-REG-02's intent. — Status:
  accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-007**: Manifests are versioned (1, 2, …) and immutable — the glossary entry for
  Manifest gains "versioned; each version immutable" (no new term; forbidden synonym:
  Revision); a replacement creates the next
  version and keeps the old; submitting content equal to the current version creates no
  version and no audit row. — Why: Eval Runs and Baselines (immutable) must point at the
  configuration they ran. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-008**: Concurrent replacements: the request names the version it replaces; a stale
  version is refused with a conflict (409). — Why: no silent lost update. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-009**: Product page shows only what exists in 001: Baseline (slice 004) and Eval Run
  history (slice 003) are omitted, not shown as empty placeholders. — Why: no dead seams in
  the UI. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-010**: Audit action `manifest_replaced`; details: Product ID, client ID, from and to
  version numbers, names of the top-level sections that changed. — Why: the audit-action
  registry is append-only and guarded; content never enters audit details. — Status:
  accepted (owner, 2026-10-30, Gate B part 1, D-017). Version 1 (created by the seed through the same service) writes
  `manifest_created` with the seeded administrator as actor, so every Manifest version has
  exactly one audit row.
- **PP-011**: Provider value set for the PoC: `mock`, labelled "Mock provider"; Model
  Binding role labels "Generation", "Judge", "Embedding". — Why: D-012 label maps; the
  provider set is not in the glossary. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-012** *(Fork B3 = A)*: the Manifest's `product` section must name the Product it is
  submitted for; a mismatch is refused. — Why: a Manifest must not move a Product to another
  client or project. — Status: accepted (owner, 2026-10-30, Gate B part 1, D-017).
- **PP-013**: `client_id` and `project_id` are human-readable slugs (`acme`,
  `support-bot`: lower case, digits, `-`), `project_id` unique within its client; rows also
  carry a UUID primary key (database rules). — Why: the brief's identifiers are slugs; the
  Manifest and the CLI (`--product acme/support-bot`) name Products by them. — Status:
  accepted (owner, 2026-10-30, Gate B part 1, D-017).

## Open questions *(mandatory; may be "none")*

- **OQ-001**: Forks B1–B4 above. — Resolved: option A for all four (owner, 2026-10-30, D-017).
- **OQ-002**: What is an "owner" in the registry module (brief §5) — a Product owner, a
  Golden owner (brief §6.3), a Notification recipient? — Decides: owner, at the slice that
  first needs it. — Blocks: nothing in 001.
- **OQ-REG-01 / OQ-REG-02**: answered by Forks B2 / B1.

## Assumptions

- Recon (Phase 1) confirms, before the contract: whether the template already separates the
  migration-owner role from the app role (for BYPASSRLS), and how the per-request tenant
  setting stays scoped to one transaction with pooled connections.
- The Manifest validation and the API are contract-shaped: after this spec is approved and
  recon is done, the contract returns to the owner for approval (Gate B part 2, brief §9)
  before the test-author writes the sealed oracle. The web page takes the classic path.
- Baseline and Eval Run history join the Product page in slices 004 and 003.
