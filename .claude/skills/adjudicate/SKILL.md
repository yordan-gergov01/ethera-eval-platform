---
name: adjudicate
description: Take every review finding and adversarially try to refute it against the actual source; deduplicate; classify CONFIRMED / QUALIFIED / REFUTED with evidence; re-judge severity with the Bible's rubric; mark committed vs uncommitted (Bible Phase 6c). Read-only.
allowed-tools: Read, Grep, Glob, Bash(git diff *), Bash(git log *), Bash(git show *), Bash(git status *)
---

# Adjudicate findings

Findings are claims, never ground truth. Your job is to try to REFUTE each one.

## Steps

1. Collect every finding from every channel (lenses, cross-vendor, owner reports).
2. Deduplicate: same root cause → one finding, all sources listed.
3. For each finding:
   - read the cited code and its callers; reproduce the failure scenario by reading (and by
     running a targeted test if one exists);
   - check `CLAUDE.md`, `docs/FIX-REGISTRY.md`, the carrier and file headers for documented
     deliberate behaviour;
   - classify: **CONFIRMED** (scenario reproduced), **QUALIFIED** (real, but narrower or
     different than claimed — state the corrected claim), **REFUTED** (evidence that the
     scenario cannot happen or is by design);
   - re-judge severity with `.claude/rules/review.md` (critical / major / minor); when in
     doubt, the higher class;
   - committed or uncommitted (`git log`/`git diff`): decides registry treatment.
4. Discard speculative findings that name no concrete failure scenario.

## Output (fixed shape)

```
| # | Finding (one line) | Sources | Verdict | Severity | Evidence (file:line / command → output) | Committed? |
Confirmed for the fix stage: <ids>
Refuted: <ids> (each with its evidence above)
```
