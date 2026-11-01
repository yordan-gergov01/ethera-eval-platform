# Feature Specification: Demo target and Dataset

**Feature Branch**: `002-demo-target-and-dataset` (D-019)

**Created**: 2026-11-01

**Status**: Approved at HUMAN GATE B part 1 (owner, 2026-11-01, D-024): Forks D1–D4 = A,
PP-201–PP-211 accepted. The contract returns at Gate B part 2.

**Input**: Brief §9 slice 2: "`002-demo-target-and-dataset` — the demo target with seeded
mocks, retrieval modes and versioned instruction sets; Datasets and Goldens with versioning;
seed data." Brief §6.1–6.9 (the demo product, its behaviour per configuration, the seeded
Dataset and the scenarios it must make possible), §7.1 (the `demo_target` service and the
`sandbox` network).

## Domain constraints (authoritative) *(mandatory)*

- **Bounded context(s)**: this gate **accepts `evaluation` as a bounded context** (prefix
  `eval_`; in this slice it owns Datasets and Goldens only) and confirms the context-map edge
  `evaluation → registry` (a Dataset belongs to a Product). `demo_target` is an external
  system (the client's product), not a bounded context: it imports nothing from this
  repository (architecture rules).
- **Glossary terms used**: Product, Golden, Dataset (`Dataset`, `DatasetVersion`), Metric (as
  the name of a failure type's check only; Metrics are built in 003), Model Binding.
  "Instruction set", "retrieval mode" and "decision" are proposed terms (PP-201).
- **Accepted invariants that apply** (docs/domain/carriers/evaluation.md):
  - INV-EVAL-04: A Dataset version never changes after publication; Goldens are never edited
    in place.
  - Golden = input, expected outcome (decision + the rule behind it), failure type, optional
    context; a Golden that no code change can fix names an owner outside engineering.
  - Golden content is personal-data-class (privacy rules): never logged, never in audit
    details, never in metrics labels.
- **Tenancy (D-014, D-022)**: Datasets, Dataset versions and Goldens are client-owned: each
  table carries `client_id` NOT NULL with RLS ENABLE + FORCE through the client-set setting;
  explicit client filters in repositories **and in JOINs**; another Client's Product answers
  the same 404 as a missing one (PP-004 of 001); a tenant-isolation test per endpoint and per
  data-access function, proving the filter and row security each on their own (the F1 lesson
  of 001).
- **Language (D-012)**: English UI; every machine value shown (decision, failure type, owner)
  through a `Record<Value, Label>` map keyed on the generated API types (the F2 lesson of 001).
- **Domain events produced / consumed**: **none.** `DatasetVersionPublished` has no consumer
  and is dropped, as the carrier says.

## User Scenarios & Testing *(mandatory)*

Actors: **Ethera staff** with a Client Membership (as in 001). The demo target has no human
user: its caller is the runner (slice 003) and, in this slice, its golden-sample tests.

### User Story 1 — See a Product's Dataset (Priority: P1)

A staff member opens `acme / support-bot` and sees its Dataset: the current version, when it
was published, and how many Goldens it holds per failure type. They open the Dataset and read
every Golden: input, expected decision, the rule behind it, failure type, context and, where
set, its owner.

**Why this priority**: The Dataset is what every Eval Run (003) and Comparison (004) measures
against; the demo story starts with "here are the questions we hold the assistant to".

**Independent Test**: With the seed, open the Dataset of `acme / support-bot`: version 1 with
every seeded Golden; the counts per failure type match the seed.

**Acceptance Scenarios**:

1. **Given** the demo seed and a member of `acme`, **When** they open the Product page,
   **Then** it shows Dataset version 1, its publication time and the Golden count per failure
   type.
2. **Given** the same, **When** they open the Dataset, **Then** every Golden of the version is
   listed with input, expected decision, rule, failure type, context and owner where set —
   labels through their maps, all text rendered as plain text, never HTML.
3. **Given** a member of client A only, **When** they request client B's Dataset, **Then**
   the answer equals "Product not found" (PP-004 of 001).
4. **Given** a Dataset with versions 1 and 2, **When** a member asks for version 1, **Then**
   they get version 1 exactly as published (INV-EVAL-04).

### User Story 2 — A demo product that behaves as the brief describes (Priority: P1)

The demo target plays the client's product: given a customer question and the configuration
it was started with (generation model, instruction-set version, retrieval mode), it answers
from its help-center documents and its order tool, returning the answer, the retrieved
document IDs, the facts it used, its decision and token counts — deterministically.

**Why this priority**: Without it nothing can be evaluated in 003; its configured weaknesses
are what the demo's Comparisons reveal.

**Independent Test**: Golden-sample tests call the demo target in each configuration and
compare its responses with pinned expected responses; a scenario-matrix test (FR-210) checks
every seeded Golden against every demo configuration.

**Acceptance Scenarios** (brief §6.2, under the behaviour rules of PP-206):

1. **Given** `mock-gen-small-v1`, **When** asked "I bought these 5 weeks ago, can I return
   them?", **Then** it approves the return (wrong date math against the 30-day window).
2. **Given** `mock-gen-small-v1` with instruction set v1, **When** asked something no document
   or tool covers, **Then** it answers anyway with a fact found in no retrieved document.
3. **Given** `mock-gen-small-v2` + `keyword`, **When** asked the 5-weeks question, **Then** it
   denies the return; **When** asked "How do I send them back?", **Then** it still misses the
   return-policy document.
4. **Given** `semantic` retrieval, **When** asked "How do I send them back?", **Then** it
   retrieves the return-policy document.
5. **Given** `mock-gen-medium-v1`, **Then** it answers the seeded questions best, at about
   2.5× the cost per call of the small models (prices × tokens, PP-207) and with higher
   latency.
6. **Given** any configuration and the same input, **When** called twice, **Then** both
   responses are identical, `latency_ms` included (PP-207).
7. **Given** instruction-set version 2, **Then** the behaviour differs from version 1 only as
   PP-206 rule R4 says, and the instruction set is read from its `.md` file on every
   construction (Bible, prompt-fix round).

### Edge Cases

- A Dataset version that does not exist: 404 `DATASET_VERSION_NOT_FOUND` (PP-209).
- A Product without a Dataset (reachable only in tests) — PP-208.
- A configuration the demo target does not know (model, instruction-set version, retrieval
  mode): it refuses to start, never falls back to a default.
- A very long question to the demo target: refused by size (security rules, input).
- An order number the order tool does not know: the answer says so (decision `report_status`
  with status "unknown"), not an invented status.
- Golden text containing markup or instructions: plain text everywhere, never executed or
  rendered (security rules: untrusted content).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-201**: The system MUST hold one Dataset per Product, published as immutable numbered
  versions (1, 2, …), each holding its Goldens in a fixed order (INV-EVAL-04, PP-208).
- **FR-202**: A Golden MUST hold input, expected decision (PP-202), rule (PP-204), failure type
  (PP-203) and optional context (accepted), plus the proposed optional `expected_numbers`
  (PP-204), `owner` and `unfixable_by_code` (PP-205).
- **FR-203**: The system MUST seed Dataset version 1 of `acme / support-bot` (about 20 Goldens,
  the archetypes of PP-211), idempotently.
- **FR-204**: Members MUST be able to read a Product's Dataset summary (current version,
  publication time, counts per failure type) and any published version in full, and nothing
  of other Clients' Datasets — by explicit filters and by row security, each proven alone.
- **FR-205**: The demo target MUST answer `POST /chat` with `answer`, `retrieved_doc_ids`,
  `facts_used`, `decision`, input and output token counts and `latency_ms`, for the
  configuration it was started with.
- **FR-206**: The demo target's behaviour MUST follow PP-206 deterministically, and it MUST
  read its instruction set from a versioned `.md` file on every construction.
- **FR-207**: Every instruction set MUST have golden-sample tests pinned to its version, the
  response schema and the mock model (testing rules).
- **FR-208**: The demo target MUST import nothing from this repository; when it runs, it runs
  only on the internal `sandbox` network (Fork D1).
- **FR-209**: Golden content MUST never reach logs, audit details or metrics labels.
- **FR-210**: A scenario-matrix test MUST pin, for every seeded Golden, its expected pass/fail
  (by decision and, where set, numbers) under each demo configuration of brief §6.4–6.8, and
  prove the outcomes of PP-211 (which scenario fixes which Golden, zero regressions where the
  brief requires them). It reads the seed and the demo target's real responses; Metrics proper
  arrive in 003 and must agree with it.

### Key Entities

- **Dataset** (`evaluation`): one per Product; `client_id`, Product reference.
- **Dataset version** (`DatasetVersion`): `client_id`, Dataset reference, number, publication
  time; immutable. (No publisher field while only the seed publishes — Fork D2.)
- **Golden**: `client_id`, Dataset-version reference, position, input, expected decision,
  rule, failure type, context (optional); proposed: `expected_numbers`, `owner`,
  `unfixable_by_code` (PP-204, PP-205).
- **Demo target configuration** (outside the backend): generation model ID, instruction-set
  version, retrieval mode.
- **Demo target data** (outside the backend): help-center documents (ID, title, text), the
  order fixture (number, status), the mock-model table (model ID, prices per 1M input and
  output tokens, latency distribution, behaviour flags of PP-206).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-201**: 0 cross-client reads in the tenant-isolation tests of every new endpoint and
  data-access function; with either the explicit filter or row security removed, the other
  still keeps other Clients' rows out.
- **SC-202**: Every seeded Golden appears on the Dataset page with all its fields.
- **SC-203**: Each behaviour of brief §6.2 has at least one golden-sample test per
  configuration it names; two consecutive runs give byte-identical responses.
- **SC-204**: The scenario-matrix test (FR-210) shows, against the Baseline configuration
  `mock-gen-small-v1` + `keyword` + instruction set v1: the instruction-set Candidate (§6.5)
  fixes at least one Golden, leaves at least one still failing, and turns no passing Golden
  into a failing one; the retrieval Candidate (§6.6) turns the retrieval-dependent date-math
  Golden (PP-211 G2) into a pass; the unfixable Golden (G5) fails under every configuration.
- **SC-205**: 0 occurrences of seeded Golden text in captured logs over the slice's flows.

## Forks for the owner (HUMAN GATE B)

Each fork is a genuine choice with consequences; my recommendation comes first.

### Fork D1 — The demo target before its caller exists

The demo target's only real caller, the runner, arrives in slice 003; the house rules forbid
an endpoint without a caller.

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | Build the demo target in 002 as the brief orders, with its golden-sample and scenario-matrix tests; its compose service arrives in 003 with the runner's sandbox launcher. Recorded as a dated deviation (like D-006), closed by slice 003. | Behaviour and seed are designed and checked together (SC-204); `docker compose up` shows no demo target until 003; one dated ledger line. |
| B | Build it and add its compose service now. | A running container no one can call (the sandbox network is internal): a live dead seam. |
| C | Move the demo target to 003. | 002 shrinks to Datasets; the seed cannot be checked against real behaviour until 003; 003 grows. |

### Fork D2 — How Goldens get into a Dataset

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | Seed only in 002; read-only API and pages. | Smallest slice; the demo uses the seeded Dataset; no audit action and no publisher field yet. |
| B | An admin endpoint and form "Add Golden" publishing the next version (append-only, audited). | More surface: write Permission, audit action, a validation contract, a publisher field (personal data, erasure cascade); shows INV-EVAL-04 live. |

### Fork D3 — Does the Manifest name the demo target's configuration now?

Manifest sections are added by the slice that first consumes them (Fork B3 of 001).

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | No Manifest change in 002. One Dataset per Product needs no pointer; the target configuration (instruction-set version, retrieval mode) joins the Manifest in 003, where the runner first consumes it. | No section without a consumer; the Product page shows the full configuration from 003. |
| B | Add `target: {instruction_set, retrieval}` and `dataset` sections now. | The Product page can show the configuration now; the sections have no consumer until 003. |

### Fork D4 — The brief's §6.6 sentence

Brief §6.6: "a Candidate changing only retrieval to `semantic` → the date-math Golden becomes
always pass." Brief §6.2 puts the date-math bug in `mock-gen-small-v1` itself, which a
retrieval change cannot fix.

| Option | Means | Consequences |
|---|---|---|
| **A (recommended)** | Keep the sentence true with two date-math Goldens (PP-211): G1, the model's arithmetic bug (fixed by `mock-gen-small-v2`, the model-release scenario); G2, a date question phrased so keyword search misses the return policy and the model falls back to an invented window — semantic retrieval finds the policy and G2 becomes always pass. | Every brief scenario holds as written (scenario matrix, SC-204); one more Golden. |
| B | Read §6.6 as "the retrieval-miss Golden" and record a dated deviation from the brief. | Simpler seed; the demo script says something different from the brief. |

## Proposed policies *(mandatory; may be "none")*

- **PP-201**: Glossary additions: **Instruction set** — the versioned `.md` file of
  instructions the Product's generation model receives (`InstructionSet`; forbidden synonym in
  code: Prompt template); **Retrieval mode** — how the Product finds documents, values
  `keyword`, `semantic` (`RetrievalMode`); **Decision** — the action a Product's answer commits
  to, one value of the decision set (`Decision`). — Why: the brief uses these words in the
  Change kinds (§6.5–6.6) and in Goldens. — Status: accepted (owner, 2026-11-01, D-024).
- **PP-202**: Decision value set, global for the PoC and owned by `evaluation` (a value set on
  the Golden): `approve_return`, `deny_return`, `explain_return`, `approve_refund`,
  `deny_refund`, `report_status`, `answer_from_docs`, `escalate`, labelled in the web app. The
  demo target keeps its own copy (it imports nothing); a test that may import both proves the
  sets are equal. The seed validates every Golden's decision against the set (the only write
  path, Fork D2 = A). — Why: Goldens hold "decision + rule"; `policy_correct` compares
  decisions in 003. — Status: accepted (owner, 2026-11-01, D-024).
- **PP-203**: Failure type value set, each with its Metric (the guideline gains the proposed
  rows): `date_math` → `policy_correct`; `refund_rules` → `policy_correct`; `invented_facts` →
  `stays_in_docs`; `out_of_docs` → `offers_human_when_unknown`; `retrieval_miss` (new) →
  `policy_correct` on the expected decision (finding the right document is what makes
  `explain_return` correct); `order_status_tool` → `policy_correct` with tool context (already
  proposed in the guideline). — Why: one failure type per Golden, one Metric per failure type,
  results sliced by it. — Status: accepted (owner, 2026-11-01, D-024).
- **PP-204**: A Golden's `rule` is short plain text naming the policy and its source document
  ID where one exists ("Returns within 30 days of delivery — doc `returns`"); the optional
  `expected_numbers` lists numbers the rule implies (`30`, `49.90`) for `policy_correct` in
  003. — Why: the accepted "decision + the rule behind it" needs a shape. — Status: accepted (owner, 2026-11-01, D-024).
- **PP-205**: Golden `owner` (optional): a team from a closed set for the PoC, `engineering` or
  `support_content`, labelled in the web app; `unfixable_by_code` (default false) — when true,
  `owner` is required and is not `engineering`. The context map changes accordingly: Golden
  owners → `evaluation`; Product owners stay with `registry` (OQ-002 stays open for them). —
  Why: brief §6.3; a team, not a person, so no personal data. — Status: accepted (owner, 2026-11-01, D-024).
- **PP-206**: Demo-target behaviour rules (deterministic; data in the demo target's own
  tables):
  - **R1 Retrieval.** `keyword` returns the documents sharing a keyword with the question;
    `semantic` returns those plus documents matched through a synonym table ("send them back"
    → `returns`). Semantic is a superset of keyword.
  - **R2 Arithmetic.** With the policy document retrieved, the model applies its window:
    `mock-gen-small-v1` counts a week as 5 days (the date-math bug: "5 weeks" = 25 days < 30 →
    approve); `mock-gen-small-v2` and `mock-gen-medium-v1` count 7.
  - **R3 Nothing covers the question** (no document and no tool result): with instruction set
    v1, the small models answer anyway with a fact from no retrieved document (for returns:
    "within 14 days"); `mock-gen-medium-v1` offers a human (`escalate`).
  - **R4 Instruction set v2** adds one instruction: "if neither the documents nor the tool
    result cover the question, offer a human" — every model then escalates in R3's case.
    Nothing else changes.
  - **R5 Embellishment.** The small models add one fact that is in no retrieved document to
    shipping answers ("return shipping is free"); `mock-gen-medium-v1` does not.
  - **R6 Tool.** Order questions are answered from the order fixture by every model.
  — Why: brief §6.2 and the scenarios §6.5–6.8 (checked in PP-211). — Status: accepted (owner, 2026-11-01, D-024).
- **PP-207**: Prices and latency live in the demo target's mock-model table, as the brief
  says ("each mock declares prices per 1M input/output tokens and a latency distribution"):
  `mock-gen-medium-v1` is priced so a typical call costs about 2.5× a small model's. The
  response carries token counts and `latency_ms`; `latency_ms` is sampled from the model's
  distribution with a seed of model + input only, so identical calls give identical responses
  and latency never makes a Golden product-flaky. The demo target never sleeps. How the runner
  learns the prices (in the response, or from the model table) is decided in the 003 contract.
  — Why: deterministic, fast tests; no deviation from the brief. — Status: accepted (owner, 2026-11-01, D-024).
- **PP-208**: Every Product has exactly one Dataset, created with version 1 by the seed; a
  Product without one answers the Dataset summary with `404 DATASET_NOT_FOUND` (reachable only
  in tests). — Why: glossary "a versioned set of Goldens for one Product". — Status: accepted (owner, 2026-11-01, D-024).
- **PP-209**: Endpoints (Permission `products:read`; members only; the 404 rules of 001):
  `GET /api/v1/products/{client_id}/{project_id}/dataset` — summary: current version,
  published at, counts per failure type; `GET …/dataset/versions/{n}` — the full version with
  its Goldens in order. Error codes `DATASET_NOT_FOUND`, `DATASET_VERSION_NOT_FOUND`. — Why:
  the read path of User Story 1; reading a Dataset is part of reading a Product, so no new
  Permission. — Status: accepted (owner, 2026-11-01, D-024).
- **PP-210**: Web: a new feature `evaluation` (mirroring the module, like `registry` in 001)
  owns the Dataset summary and the Dataset page; the Product page (a page, which may compose
  features) shows the registry's Product detail and the evaluation's Dataset summary side by
  side, with no import between features. The Dataset page lists the Goldens of a version as a
  table with a version selector (see `mockup.html`). — Why: the eslint feature boundary
  ("features never import other features; compose them in a page"). Brief §7.8 lists no
  Dataset view; this adds one. — Status: accepted (owner, 2026-11-01, D-024).
- **PP-211**: Seed archetypes for `acme / support-bot` (about 20 Goldens, several per
  archetype; exact texts in the contract) and their outcome per configuration (✓ pass, ✗ fail;
  Baseline B = small-v1 + keyword + v1; PR = instruction set v2; Ret = semantic; Rel =
  `mock-gen-small-v2`; Exp = `mock-gen-medium-v1`):

  | Archetype | Failure type | Expected decision | B | PR | Ret | Rel | Exp |
  |---|---|---|---|---|---|---|---|
  | G1 "5 weeks ago, can I return them?" | `date_math` | `deny_return` | ✗ (R2) | ✗ | ✗ | ✓ | ✓ |
  | G2 "3 weeks ago, can I send them back?" | `date_math` | `approve_return` | ✗ (R3: invents 14 days) | ✗ (escalates) | ✓ (R1) | ✗ | ✗ (escalates) |
  | G3 "How do I send them back?" | `retrieval_miss` | `explain_return` | ✗ | ✗ | ✓ | ✗ | ✗ |
  | G4 "Can I pay with crypto?" (no document) | `out_of_docs` | `escalate` | ✗ (R3) | ✓ (R4) | ✗ | ✗ | ✓ |
  | G5 "Do you sell gift cards?" — unfixable, owner `support_content` | `out_of_docs` | `answer_from_docs` (needs a gift-card document) | ✗ | ✗ | ✗ | ✗ | ✗ |
  | G6 "Where is order 1042?" | `order_status_tool` | `report_status` | ✓ | ✓ | ✓ | ✓ | ✓ |
  | G7 "The sole came off after a week — refund?" | `refund_rules` | `approve_refund` (49.90) | ✓ | ✓ | ✓ | ✓ | ✓ |
  | G8 "Defect noticed after 15 weeks — refund?" (90-day window) | `refund_rules` | `deny_refund` | ✗ (R2: 75 days) | ✗ | ✗ | ✓ | ✓ |
  | G9 "Is return shipping free?" | `invented_facts` | `answer_from_docs` | ✗ (R5) | ✗ | ✗ | ✗ | ✓ |

  Scenario check: PR fixes G4, leaves G1–G3, G5, G8, G9 failing, regresses nothing (§6.5:
  gate passes). Ret makes G2 (date math) and G3 pass, regresses nothing (§6.6). Rel fixes G1
  and G8, regresses nothing, same cost (§6.7 → switch). Exp fixes G1, G4, G8, G9 at about 2.5×
  cost (§6.8 → discuss). G5 fails everywhere (§6.3). — Why: the brief's scenarios must come
  out exactly as written; FR-210 pins this table. — Status: accepted (owner, 2026-11-01, D-024).

## Open questions *(mandatory; may be "none")*

- **OQ-201**: Forks D1–D4 above. — Resolved: option A for all four (owner, 2026-11-01, D-024).
- **OQ-002** (from 001): answered for Goldens by PP-205. Product owners and Notification
  recipients stay open. — Decides: owner, at the slice that first needs them (006 for
  recipients). — Blocks: nothing in 002.
- **OQ-EVAL-01 / OQ-EVAL-02**: slice 003. — Blocks: nothing in 002.

## Assumptions

- Recon confirms before the contract: the module seed order (`evaluation` seeds after
  `registry` through `ModuleMount.seed`), and how the demo target is packaged (its own
  requirements file, no imports from the repository) and tested in CI without the sandbox
  network.
- The Dataset read API and the demo target's `/chat` are contract-shaped: after approval and
  recon the contract returns to the owner (Gate B part 2) before the test-author writes the
  sealed oracle. The pages take the classic path.
- The seeded Goldens' exact texts and the documents' texts are fixed in the contract.
