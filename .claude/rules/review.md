# Review

Source: Bible Phase 6 and "Audit mode", brief §3 C8.

## Channels

1. **Cross-vendor review (Codex/GPT)** — only if the owner provides the CLI and gives explicit
   consent for the change in question (C8). Read-only, context-rich brief, no secrets, no
   tenant data. Otherwise the report states "channel (a) not run for this change".
2. **Lens reviews (always)** — read-only agents in parallel, ONE lens each:
   `security-privacy-lens`, `house-rules-lens`, `functional-spec-lens` (including vacuous
   tests), plus `domain-guard` (language, ownership, invented aggregates, proposed policies).
3. **Adjudication (always)** — the `adjudicator` agent takes EVERY finding and tries to refute
   it against the source; deduplicates; discards refuted, speculative and by-design findings;
   re-judges severity; marks committed vs uncommitted.

Reviewers report ONLY defects with a concrete failure scenario (inputs/state → wrong
outcome). No style nits, no "consider". An empty list is a respectable result.

## Classification

Every finding ends **CONFIRMED / QUALIFIED / REFUTED** with evidence (file:line, a command
and its output). Refutations are reported with the same care as fixes.

## Severity rubric

- **critical** — crosses a hard boundary regardless of likelihood: cross-client read/write;
  personal data or Golden text reaching logs, metrics, audit details or another client; an
  auth/permission gate bypassed; loss or silent corruption of evaluation results, baselines
  or spend rows; a Gate Verdict that passes a regression.
- **major** — wrong behaviour on a real path: a defect users hit in normal use, a
  spec-named invariant violated, a missing audit row, a resource-exhaustion vector, a vacuous
  seal, a Candidate with more than one Change.
- **minor** — real but contained: edge-path UX, dead seams, drift that cannot yet mislead.

When in doubt, take the higher class and let adjudication argue it down with evidence.

## Audit mode (before the demo)

Loop-until-dry: K = 2 consecutive dry rounds through different lenses with fresh contexts;
mandatory canary (a representative defect planted in a disposable worktree, never the real
tree); ceilings declared up front (rounds, time, scope); exhaustion is a report, never a
silent green. Finders never know the stopping rule.

## Mechanical checks

- The `adjudicate` skill's fixed output table; findings reach fixers only with evidence.
