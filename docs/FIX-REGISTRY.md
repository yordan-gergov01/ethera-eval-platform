# Fix registry

The project's defect memory (Bible Phase 7; rules in `.claude/rules/fix-registry.md`).

## The two-artifact rule

A fix is finished only with BOTH artifacts:

1. a **sealing regression test** named for the invariant (never the mechanism), proven by a
   mutation check — revert the fix, the seal goes red; restore it, the seal goes green; and
2. a **row in this table** — when the defect shipped (lived in committed code).

A fix with only one of them is unfinished: not done, not committed.

## Scope

- Defects that **shipped** get a row. A defect caught in a run's own uncommitted code gets
  the sealing test but no row. A committed twin found along the way gets a row.
- Before fixing anything, check this table and the `CLAUDE.md` ledger: the "bug" may be
  documented deliberate behaviour.
- A revising fix references the old ID; the old row is marked `superseded by FIX-NNN`.
  Seals are never weakened; changing a sealed invariant is an owner decision recorded in the
  superseding row.
- The commit column is filled by a follow-up commit once the fix ships.

## Registry

| ID | Date | Scenario and root cause | Found by | Seal (test name) | Severity | Commit |
|---|---|---|---|---|---|---|

*No shipped defects yet.*
