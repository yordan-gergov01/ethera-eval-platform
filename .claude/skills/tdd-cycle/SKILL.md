---
name: tdd-cycle
description: Red-green-refactor for an implementer's OWN additional tests (never for sealed oracle files). Output shows the failing run, then the passing run.
---

# TDD cycle

For tests you add beside a sealed oracle, or on the classic path. Sealed files are never
edited.

## Steps

1. **Red** — write one failing test named `test_<function>_<scenario>_<expected>` in the file
   that mirrors the source file. Run it alone; capture the failure. It must fail for the
   expected reason (assertion or missing behaviour), not an import or fixture error.
2. **Green** — the smallest production change that passes it. Run it again; capture the pass.
3. **Refactor** — improve names and structure with the test green; keep files ≤ 600 lines,
   functions ≤ 100, headers truthful.
4. **Checks** — on touched files: `ruff format`, `ruff check`, `mypy`, `lint-imports` (or
   `npm run check` for web). Targeted tests only; never two suite runs against the shared
   test database.

## Output (fixed shape)

```
RED   <test id>  <one-line failure reason>
GREEN <test id>  passed
Refactor: <what changed or "none">
Checks: ruff ✓ mypy ✓ lint-imports ✓ (or the failing tail)
```
