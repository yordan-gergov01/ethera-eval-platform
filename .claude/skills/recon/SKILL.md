---
name: recon
description: Read-only seam map before building a slice or fixing a bug (Bible Phase 1). Produces file:line anchors, templates to copy by name, bug root causes with evidence, and honest negative findings. Never edits.
allowed-tools: Read, Grep, Glob
---

# Recon (read-only)

You map the terrain; you never edit. Input: the slice spec (`specs/<slice>/spec.md`) or the
bug report, plus the question to answer.

## Steps

1. Read `CLAUDE.md` (ledger), `docs/domain/context-map.md`, the relevant carrier in
   `docs/domain/carriers/`, and `docs/FIX-REGISTRY.md`.
2. For each place the new work attaches, find the seam and quote its signature verbatim with
   `file:line`. Prefer the closest existing shape (a module already built, or
   `docs/reference/TEMPLATE_CONVENTIONS.md` anchors into the templates).
3. Name the templates to copy: "follow `<path>` 1:1, including <its states/invariants>".
4. For every reported bug: reproduce by reading (conditions, the exact broken line), and check
   whether it is documented deliberate behaviour (ledger, registry, file headers).
5. State negative findings plainly: "there is NO precedent for X; it is a new pattern and
   needs an owner call".

## Output (fixed shape)

```
## Seams
| Attaches to | file:line | Verbatim signature | Notes |
## Templates to copy
- <what> → <path>, 1:1 including <...>
## Bugs (if any)
| Claim | Root cause (file:line) | Repro conditions | Deliberate? (source) | Verdict |
## Negative findings
- ...
## Open questions for the owner
- ...
```
