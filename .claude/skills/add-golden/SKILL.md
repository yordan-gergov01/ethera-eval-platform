---
name: add-golden
description: Append a Golden (input, expected decision plus the rule behind it, failure type, optional context) to a Product's Dataset by publishing a new Dataset version. Never edits an existing Golden in place.
---

# Add a Golden

A Dataset is versioned and immutable. Adding, changing or removing a Golden always produces a
new Dataset version; Eval Runs on the old version stay comparable only with each other.

## Steps

1. Read `docs/evaluation-guideline.md` (criteria, failure types, rubric) and the Product's
   current Dataset version.
2. Write the Golden:
   - `input` — the customer message (fictional; no real personal data);
   - `expected` — a **decision** plus the **rule** behind it (cite the help-center document or
     policy), never a verbatim ideal answer only;
   - `failure_type` — one of the guideline's failure types;
   - `context` — optional (order state, dates) needed to judge it;
   - `owner` — when no code change can fix it (e.g. no document exists), the owner outside
     engineering.
3. Publish a new Dataset version containing all previous Goldens unchanged plus the new one
   (or the replacement, with the old one retired in the new version only).
4. If the Product's Baseline uses the old version, say so: a new Baseline is needed before
   Comparisons become possible again.

## Output (fixed shape)

```
Product: <client/project>  Dataset: v<old> → v<new>  Goldens: <n_old> → <n_new>
Added: <golden id>  failure type: <type>  decision: <decision>  rule: <rule>
Baseline impact: <none | new baseline needed>
```
