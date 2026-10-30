# Fix registry

Source: Bible Phase 7. The registry is `docs/FIX-REGISTRY.md`, the project's defect memory.

## The two-artifact rule

A fix is done only with BOTH:

1. a **sealing regression test** named for the invariant
   (`test_comparison_refuses_runs_with_different_dataset_versions`), never the mechanism; and
2. a **registry row** — when the defect shipped (lived in committed code).

The seal is **mutation-checked**: revert the fix, watch the seal go red, restore, watch it go
green. A seal that stays green under mutation is vacuous and is rewritten. Watch for the
subtle vacuity of equal values (a prefix check passing a re-hardcoded literal): a source-scan
guard is the real seal there.

## Before fixing anything

Check the registry and the `CLAUDE.md` ledger: the "bug" may be documented deliberate
behaviour, or a previously fixed area whose constraints explain the current shape.

## Scope

- A defect in committed code gets a row.
- A defect caught in the run's own uncommitted code gets the sealing test but NO row.
- A committed twin discovered along the way DOES get a row.

## Rows

`| ID | Date | Scenario and root cause | Found by | Seal (test name) | Severity | Commit |`

- IDs are `FIX-NNN`, never reused. The commit hash is filled by a follow-up commit once the
  fix ships; attribution stays honest (a wrong hash is corrected in its own commit).
- A fix that revises an earlier fix references the old ID; the old row is marked
  `superseded by FIX-NNN`. Seals are never weakened to let a later change pass: changing a
  sealed invariant is an owner decision recorded in the superseding row.

## Mechanical checks

- The `register-fix` skill output shows the mutation check (red, then green).
- `tests/architecture/test_docstring_headers.py` resolves every `test_*` reference, so a
  registry seal named in a header cannot silently disappear.
