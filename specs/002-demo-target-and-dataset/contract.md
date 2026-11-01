# Contract: 002-demo-target-and-dataset

The sealed-oracle contract for Datasets and the demo target (Bible Phase 2). It states WHAT
the system must do at its public surfaces, never how.

- **Sources:** `spec.md` (approved at Gate B part 1, D-024); `docs/domain/carriers/evaluation.md`
  (INV-EVAL-04 and the value sets); `docs/domain/glossary.md`; D-014/D-022 (tenancy); the slice
  001 contract (D-022) for the shared conventions it reuses.
- **Where each rule comes from:** clauses that cite a policy restate it. Clauses marked
  **[C-2nn]** are refinements chosen in this contract, listed in §8 for the owner's approval at
  Gate B part 2.
- **Terms** are the glossary's: Client, Product, Dataset, Golden, Decision, Instruction set,
  Retrieval mode, Model Binding.

## 1. Scope

**Covered (sealed):**

- The two Dataset endpoints of §2.1–2.2, with tenant isolation on both.
- The seeded Dataset of `acme / support-bot` (§3.1), observed through the API.
- The demo target's `POST /chat` (§2.3) and its start-up configuration (§3.3).
- The demo target's behaviour on every seeded Golden in each demo configuration: the scenario
  matrix (§3.4, spec FR-210, SC-204).
- Golden content never reaching the technical logs (§5).

**Out of scope for the oracle** — each item is covered elsewhere:

| Item | Covered by |
|---|---|
| Row security proven independently of the explicit filters, on all three tables; FORCE; append-only grants (INV-EVAL-04 at the database) | the implementer's own tests (database rules; the slice 001 F1 pattern) |
| Golden-sample tests of each instruction set pinned to version, schema and model (FR-207), including `answer` texts | the implementer's own tests |
| The decision value sets of the demo target and the backend being equal (PP-202) | the implementer's own test |
| The demo target importing nothing from this repository (FR-208) | an import-linter contract and its architecture test |
| Models and migrations agree; a fresh database migrates from zero | `tests/integration/test_migrations.py` |
| The Product page's Dataset section and the Dataset page (web) | the classic path: Vitest for label maps and the API client, review against `mockup.html` |
| The demo target in compose and on the `sandbox` network | slice 003 (D-024, Fork D1 = A) |
| Writing Goldens through the API | not built (D-024, Fork D2 = A) |

## 2. Surfaces

The backend conventions of the slice 001 contract §2 apply unchanged: paths under `/api/v1`,
RFC 9457 problems with `status`, `code`, `detail`, `instance`, `request_id`; ISO 8601
timestamps with a UTC offset; `detail` texts never asserted; the identifier pattern of C-1;
401 `AUTHENTICATION_FAILED` / `INVALID_TOKEN`; 403 `PERMISSION_DENIED`. Both endpoints need
`products:read` (PP-209), which both existing roles hold.

**The Product gate** (as slice 001 §2.2): `404 PRODUCT_NOT_FOUND` when there is no such
Product, when the caller is not a member of its Client, or when a path segment does not match
the identifier pattern — three bodies equal except `instance` and `request_id`. It is decided
before anything about the Dataset.

### 2.1 Read a Product's Dataset summary

`GET /api/v1/products/{client_id}/{project_id}/dataset`.

**`200`:**

```json
{
  "client_id": "acme",
  "project_id": "support-bot",
  "current_version": 1,
  "versions": [{"number": 1, "published_at": "2026-11-01T09:00:00+00:00", "golden_count": 19}],
  "failure_type_counts": {
    "date_math": 5, "refund_rules": 4, "invented_facts": 2,
    "out_of_docs": 3, "retrieval_miss": 2, "order_status_tool": 3
  }
}
```

- `versions` lists every published version, ascending by `number`; `current_version` is the
  highest **[C-201]**.
- `failure_type_counts` describes the current version and always has all six keys, zeros
  included **[C-202]**.

**`404 DATASET_NOT_FOUND`**: the Product passes the gate but has no Dataset (PP-208; reachable
only in tests).

### 2.2 Read one Dataset version

`GET /api/v1/products/{client_id}/{project_id}/dataset/versions/{number}`.

**`200`:**

```json
{
  "client_id": "acme",
  "project_id": "support-bot",
  "number": 1,
  "published_at": "2026-11-01T09:00:00+00:00",
  "is_current": true,
  "goldens": [Golden, ...]
}
```

`Golden`:

```json
{
  "position": 1,
  "input": "I bought these sneakers 5 weeks ago, can I return them?",
  "expected_decision": "deny_return",
  "rule": "Returns within 30 days of delivery — doc returns",
  "failure_type": "date_math",
  "context": null,
  "expected_numbers": ["30"],
  "owner": null,
  "unfixable_by_code": false
}
```

- `goldens` are in `position` order, positions `1..n` without gaps.
- `expected_decision` ∈ the Decision value set; `failure_type` ∈ the failure-type value set;
  `owner` is `null`, `"engineering"` or `"support_content"` (D-024).
- `expected_numbers` are decimal strings, never JSON numbers **[C-203]**; `[]` when none.
- No paging: a version is returned whole **[C-204]**.

**`404 DATASET_NOT_FOUND`** as in §2.1. **`404 DATASET_VERSION_NOT_FOUND`**: `{number}` is not
a published version — including `0`, a negative or non-numeric segment, a leading zero, or a
number beyond any version (never a `422` or a `500`, the FIX-004 lesson) **[C-205]**.

### 2.3 The demo target: `POST /chat`

The demo target is a separate HTTP application (the client's product). It is started with one
configuration (§3.3) and answers in it.

**Request:** `{"question": "<text>"}` — a string of 1–2,000 characters; unknown fields are
refused **[C-206]**.

**`200`:**

```json
{
  "answer": "<plain text>",
  "retrieved_doc_ids": ["returns"],
  "facts_used": [{"source": "returns", "statement": "Returns are accepted within 30 days of delivery."}],
  "decision": "deny_return",
  "usage": {"input_tokens": 412, "output_tokens": 58},
  "pricing": {"input_per_million": "0.20", "output_per_million": "0.80", "currency": "USD"},
  "latency_ms": 734
}
```

- `retrieved_doc_ids`: the help-center documents retrieved, plus `"tool:orders"` when the
  order tool was called **[C-207]**; ordered by ID.
- `facts_used`: every fact the answer asserts, each with the `source` it came from — a
  retrieved document ID or `"tool:orders"` — or `null` when it came from no source (an
  invented fact) **[C-208]**.
- `decision` ∈ the Decision value set (D-024).
- `usage`: integers > 0; they do not depend on the model **[C-209]**.
- `pricing`: the model's declared prices per million tokens, as decimal strings (PP-207)
  **[C-210]**.
- `latency_ms`: an integer from the model's range (§3.3); simulated, never waited.

**Refusals:** a body that is not a JSON object with exactly a valid `question` → `422`.

## 3. Semantics

### 3.1 The seed

At start-up, once the registry has seeded `acme / support-bot`, its Dataset exists with version
1 holding exactly the 19 Goldens of §3.5, in that order (FR-203). The seed is create-only and
idempotent: a second start changes nothing (same versions, same `published_at`).

### 3.2 Versions (INV-EVAL-04)

- Versions are numbered 1, 2, … per Dataset, without gaps.
- A published version never changes: after a later version is published, `GET …/versions/1`
  answers exactly as before (bodies equal), except `is_current`, which turns `false`
  (erratum, owner 2026-11-01, D-025).
- `is_current` is true only for the highest number.

### 3.3 Demo-target configuration, models and documents

**Start-up configuration** (one per process): generation model, instruction-set version,
retrieval mode. Known values:

| Setting | Values |
|---|---|
| model | `mock-gen-small-v1`, `mock-gen-small-v2`, `mock-gen-medium-v1` |
| instruction set | `v1`, `v2` |
| retrieval mode | `keyword`, `semantic` |

An unknown value refuses to start; there is no default **[C-211]**.

**Models** **[C-210]**:

| Model | input / output price per 1M tokens (USD) | `latency_ms` range |
|---|---|---|
| `mock-gen-small-v1` | 0.20 / 0.80 | 400–1,200 |
| `mock-gen-small-v2` | 0.20 / 0.80 | 400–1,200 |
| `mock-gen-medium-v1` | 0.50 / 2.00 | 1,500–3,500 |

So a call to the medium model costs exactly 2.5× the same call to a small one (C-209).

**Help-center documents** (IDs): `returns`, `refunds`, `shipping`. **Order fixture:** order
`1042` is `shipped`, `1077` is `delivered`; any other number is `unknown`. The documents state,
among other things: returns are accepted within 30 days of delivery; return shipping costs
4.90, deducted from the refund; items damaged on arrival or defective within 90 days of
delivery are refunded in full; worn items are refunded only when defective; refunds arrive in
5–7 business days. No document covers payment methods, discounts or gift cards.

**Determinism:** the same configuration and the same `question` give byte-identical response
bodies, `latency_ms` included, across calls and process restarts (spec AC 2.6).

### 3.4 The scenario matrix (spec FR-210, SC-204; PP-206, PP-211)

Configurations:

| Name | Model | Instruction set | Retrieval |
|---|---|---|---|
| B (Baseline, §6.4) | `mock-gen-small-v1` | `v1` | `keyword` |
| PR (§6.5) | `mock-gen-small-v1` | `v2` | `keyword` |
| Ret (§6.6) | `mock-gen-small-v1` | `v1` | `semantic` |
| Rel (§6.7) | `mock-gen-small-v2` | `v1` | `keyword` |
| Exp (§6.8) | `mock-gen-medium-v1` | `v1` | `keyword` |

**A response passes a Golden** **[C-212]** iff its `decision` equals the Golden's
`expected_decision` **and** every element of `facts_used` has a non-null `source` that is in
`retrieved_doc_ids`. (Numbers and answer texts are judged by Metrics in slice 003.)

The outcome of each seeded Golden (§3.5) in each configuration is exactly this (✓ passes,
✗ fails):

| # | B | PR | Ret | Rel | Exp |
|---|---|---|---|---|---|
| 1 | ✗ | ✗ | ✗ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | ✗ | ✗ | ✗ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 5 | ✗ | ✗ | ✓ | ✗ | ✗ |
| 6 | ✗ | ✗ | ✓ | ✗ | ✗ |
| 7 | ✗ | ✗ | ✓ | ✗ | ✗ |
| 8 | ✗ | ✓ | ✗ | ✗ | ✓ |
| 9 | ✗ | ✓ | ✗ | ✗ | ✓ |
| 10 | ✗ | ✗ | ✗ | ✗ | ✗ |
| 11 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 12 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 13 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 14 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 15 | ✗ | ✗ | ✗ | ✓ | ✓ |
| 16 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 17 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 18 | ✗ | ✗ | ✗ | ✗ | ✓ |
| 19 | ✓ | ✓ | ✓ | ✓ | ✓ |

What the brief's scenarios read from it: PR fixes 8 and 9 and turns no ✓ of B into ✗ (§6.5:
fixed and still-failing, zero regressions); Ret turns the date-math Golden 5 into ✓ (§6.6),
plus 6 and 7, with no regression; Rel fixes 1, 3 and 15 with no regression at equal prices
(§6.7); Exp fixes 1, 3, 8, 9, 15 and 18 at 2.5× the cost (§6.8); Golden 10 fails everywhere
(§6.3).

**Behaviour the matrix rests on** (PP-206, restated as observable facts):

- R1: Golden 5's, 6's and 7's questions retrieve `returns` under `semantic` and no document
  under `keyword`.
- R2: under `mock-gen-small-v1`, a span given in weeks is counted as 5 days a week.
- R3: with no document and no tool result, instruction set `v1` small models answer with a
  fact whose `source` is `null`; `mock-gen-medium-v1` answers `escalate`.
- R4: under instruction set `v2`, with no document and no tool result, every model answers
  `escalate`; all other answers equal those under `v1`.
- R5: for Golden 18, the small models' `facts_used` include a fact with `source: null`.
- R6: order questions call the order tool under every configuration.

### 3.5 The seeded Goldens of `acme / support-bot`, version 1

`context` is `null` and `unfixable_by_code` is `false` unless stated; `owner` is `null` unless
stated.

| # | `input` | `expected_decision` | `rule` | `failure_type` | `expected_numbers` |
|---|---|---|---|---|---|
| 1 | I bought these sneakers 5 weeks ago, can I return them? | `deny_return` | Returns within 30 days of delivery — doc returns | `date_math` | `30` |
| 2 | My boots were delivered 40 days ago. Can I still return them? | `deny_return` | Returns within 30 days of delivery — doc returns | `date_math` | `30` |
| 3 | I received my order 6 weeks ago, can I return it? | `deny_return` | Returns within 30 days of delivery — doc returns | `date_math` | `30` |
| 4 | Bought them 10 days ago, can I return them? | `approve_return` | Returns within 30 days of delivery — doc returns | `date_math` | `30` |
| 5 | I got these 3 weeks ago, can I send them back? | `approve_return` | Returns within 30 days of delivery — doc returns | `date_math` | `30` |
| 6 | How do I send them back? | `explain_return` | Return steps — doc returns | `retrieval_miss` | — |
| 7 | What's the process to ship my shoes back to you? | `explain_return` | Return steps — doc returns | `retrieval_miss` | — |
| 8 | Can I pay with crypto? | `escalate` | No document covers payment methods; offer a human | `out_of_docs` | — |
| 9 | Do you offer student discounts? | `escalate` | No document covers discounts; offer a human | `out_of_docs` | — |
| 10 | Do you sell gift cards? | `answer_from_docs` | Gift-card policy — document to be written by the support content team | `out_of_docs` | — |
| 11 | Where is order 1042? | `report_status` | Status from the order tool | `order_status_tool` | — |
| 12 | What's the status of order 1077? | `report_status` | Status from the order tool | `order_status_tool` | — |
| 13 | Where is order 9999? | `report_status` | Status from the order tool; unknown orders are reported as unknown | `order_status_tool` | — |
| 14 | The sole came off after a week. Can I get a refund? | `approve_refund` | Defects within 90 days of delivery: full refund — doc refunds | `refund_rules` | `90` |
| 15 | I noticed a defect after 15 weeks. Can I get a refund? | `deny_refund` | Defects within 90 days of delivery: full refund — doc refunds | `refund_rules` | `90` |
| 16 | My shoes arrived damaged yesterday, do I get my money back? | `approve_refund` | Damaged on arrival: full refund — doc refunds | `refund_rules` | — |
| 17 | I wore the shoes outside and changed my mind. Can I get a refund? | `deny_refund` | Worn items are refunded only when defective — doc refunds | `refund_rules` | — |
| 18 | Is return shipping free? | `answer_from_docs` | Return shipping costs 4.90, deducted from the refund — doc returns | `invented_facts` | `4.90` |
| 19 | How long does a refund take? | `answer_from_docs` | Refunds arrive in 5–7 business days — doc refunds | `invented_facts` | `5`, `7` |

Golden 10: `owner: "support_content"`, `unfixable_by_code: true`.

## 4. Refusals

- Every refusal of §2.1–2.2 (401, 403, 404) changes nothing and reveals nothing: a non-member's
  `404` equals the one for a missing Product (except `instance`, `request_id`).
- The demo target's `422` produces no answer and no `latency_ms`.

## 5. Privacy and audit

- **Audit:** none. No user writes a Dataset in this slice (Fork D2 = A); the seed writes no
  audit row, so the slice 001 seed's audit rows are unchanged **[C-213]**.
- **Logs:** no Golden `input`, `rule`, `context` or `expected_numbers` value appears in any
  backend log line; a unique marker string placed in an arranged Golden's `input` and `rule`
  never appears in the captured output, while the requests that returned it succeeded (anchor
  against a vacuous pass). The demo target logs no `question` and no `answer` **[C-214]**.

## 6. Fixtures available

**Existing**, unchanged: everything in slice 001 contract §6, including
`tests/integration/registry_fixtures.py` (`started_platform_app`, `platform_app`,
`arrange_client`, `arrange_membership`, `arrange_product`, `demo_document`).

**Provided by the implementer** in `ethera-eval-core/tests/integration/evaluation_fixtures.py`
(unsealed; the oracle relies on exactly these signatures):

| Fixture or function | Behaviour |
|---|---|
| `async def arrange_dataset_version(settings, client_id: str, project_id: str, goldens: list[dict[str, object]]) -> int` | publishes the next version of the Product's Dataset (creating the Dataset at version 1 if it has none) through the same path the seed uses; each dict has the §2.2 Golden fields except `position`; returns the new number |
| `@asynccontextmanager async def demo_target_client(model: str, instruction_set: str, retrieval: str) -> AsyncIterator[httpx.AsyncClient]` | the demo target started with that configuration, in process; entering it with an unknown value raises an exception |
| `@asynccontextmanager async def demo_target_logs(model: str, instruction_set: str, retrieval: str) -> AsyncIterator[tuple[httpx.AsyncClient, Callable[[], str]]]` | as above, plus a function returning everything the demo target has logged so far |

The oracle checks each helper through a public surface before relying on it (an arranged
version is read back through §2.2).

## 7. Instruction to the test author

Enumerate the further edge cases this contract implies and seal them; list the
underdetermined cases you did NOT seal. Cover in particular:

- **The scenario matrix** of §3.4: every cell, from real `/chat` responses and the §3.5 seed
  read through §2.2 (not a re-typed copy), so a seed and a behaviour that drift apart fail.
- **Determinism:** each §3.5 question twice per configuration, and across two
  `demo_target_client` entries: byte-identical bodies.
- **Cost and latency:** for one question, medium/small cost ratio exactly 2.5; every
  `latency_ms` inside its model's range.
- **Version boundaries:** `versions/1`, `versions/2` after an arranged version, `0`, `-1`,
  `01`, `1.0`, `abc`, `99999999999999999999` → the §2.2 answers.
- **Immutability:** version 1's body before and after arranging version 2 is equal except
  `is_current` (§3.2); the
  summary's `current_version` and counts follow the new version.
- **Tenant isolation** on both endpoints, for a member of A only, an admin who is a member of B
  only, and a user with no memberships.
- **The seed:** present after start; unchanged after a second start.
- **`/chat` refusals:** empty, 2,000- and 2,001-character questions, a missing or extra field,
  a non-object body; unknown configuration values on entry.
- **Logs:** markers absent, anchors present.

## 8. Contract-level choices for the owner (Gate B part 2)

| ID | Choice | Alternative |
|---|---|---|
| C-201 | the summary lists all versions (for the version selector) | a separate list endpoint |
| C-202 | `failure_type_counts` always has all six keys | only the non-zero ones |
| C-203 | `expected_numbers` are decimal strings | JSON numbers (float risk) |
| C-204 | a version is returned whole, no paging | paging like the Products list |
| C-205 | any segment that is not a published version's number → the same 404, never 422/500 | 422 for non-numeric segments |
| C-206 | `/chat` takes only `question`, 1–2,000 characters | a conversation history |
| C-207 | the order tool appears as source `"tool:orders"` in `retrieved_doc_ids` | a separate `tool_calls` field |
| C-208 | every asserted fact carries its `source`, `null` for an invented one (what `stays_in_docs` will read in 003) | facts as plain strings |
| C-209 | token counts do not depend on the model, so cost differences come from prices only | per-model token counts |
| C-210 | the demo target returns its prices in every response, with the table of §3.3 (this pre-answers PP-207's "how the runner learns the prices": from the response) | prices only in the demo target's data, read by the runner some other way in 003 |
| C-211 | an unknown configuration value refuses to start | a default configuration |
| C-212 | the matrix pass rule: decision equal and every fact sourced from a retrieved source | decisions only |
| C-213 | no audit row for seeded Datasets | an audit action `dataset_version_published` for the seed |
| C-214 | the demo target logs no question and no answer | log them (they would be Golden text in 003) |

Status: approved — owner, 2026-11-01, HUMAN GATE B part 2 (D-025): C-201 to C-214 as written.
