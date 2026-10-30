---
name: register-fix
description: Fix a CONFIRMED finding with an invariant-named sealing test, mutation-check the seal (revert, see red, restore, see green), and add a docs/FIX-REGISTRY.md row when the defect shipped (Bible Phase 7).
---

# Register a fix

Input: one CONFIRMED finding with its adjudication evidence. Check the registry first: it may
supersede an earlier fix.

## Steps

1. **Seal first**: write a test named for the INVARIANT
   (`test_<invariant_in_words>`), in the mirrored test file. Run it: it must FAIL on the
   current code for the finding's reason.
2. **Fix**: the smallest production change. Run the seal: GREEN.
3. **Mutation check**: revert the fix only (`git stash` the production hunk or reverse it
   by hand), run the seal: RED. Restore the fix: GREEN. A seal that stays green under the
   mutation is vacuous — rewrite it (consider a source-scan guard).
4. **Registry** (`docs/FIX-REGISTRY.md`), only if the defect lived in committed code (or is a
   committed twin): append `| FIX-NNN | <date> | <scenario + root cause> | <found by> |
   <seal test name> | <severity> | pending |`. If it revises an earlier fix, reference the
   old ID and mark the old row `superseded by FIX-NNN`.
5. Checks on touched files; targeted tests only.

## Output (fixed shape)

```
Finding: <id>  Severity: <...>  Shipped: yes/no
Seal: <test name>
  before fix:   RED   (<reason>)
  after fix:    GREEN
  fix reverted: RED   (mutation check)
  restored:     GREEN
Registry: FIX-NNN added | no row (uncommitted) 
```
