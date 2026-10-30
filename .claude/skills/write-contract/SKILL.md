---
name: write-contract
description: Write a sealed-oracle contract for contract-shaped work (Bible Phase 2) — WHAT the system must do, never HOW. Use after the owner approved the spec (HUMAN GATE B, part 1) and recon is done; the contract then returns to the owner for approval (GATE B, part 2, brief §9) before the test-author writes the oracle.
---

# Write the contract

Output: `specs/<slice>/contract.md`. It is the quality bottleneck of the sealed path: a vague
contract yields an impossible or hole-filled oracle.

## Rules

- WHAT, never HOW: no module names, no class names, no library choices, no schema or table
  hints. Only public surfaces: HTTP endpoints, broker messages, CLI commands and exit codes,
  files read/written.
- Use the glossary terms exactly (`docs/domain/glossary.md`).
- Only ACCEPTED rules from the carrier; proposed policies are not contracted until accepted.
- Every clause is testable from outside.

## Sections (fixed)

1. **Scope** — the surfaces covered; what is explicitly out of scope.
2. **Surfaces** — per endpoint: verb, path, permission, request shape (types, bounds, unknown
   fields rejected), every response status with its exact body shape and problem `code`.
   Per message: type, envelope, payload fields. Per CLI: arguments, stdout shape, exit codes.
3. **Semantics** — invariants (cite carrier IDs), ordering, idempotency, numbering,
   determinism (seeds), concurrency guarantees.
4. **Refusals** — every refusal with status/code, and what it must NOT consume or change.
5. **Privacy and audit** — which actions write an audit row, with which fields (no personal
   data); what never appears in logs.
6. **Fixtures available** — public surfaces the test author may use to arrange state.
7. **Instruction to the test author** — "Enumerate the further edge cases this contract
   implies (boundaries at their own boundary, concurrency, refusals that must not consume
   resources, determinism across runs) and list the underdetermined cases you did NOT seal."

End with `Status: draft — awaiting owner approval (HUMAN GATE B)`.
