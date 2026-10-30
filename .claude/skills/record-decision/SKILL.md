---
name: record-decision
description: Record an owner decision, deliberate deviation or resolved conflict — a D-NNN entry in docs/DECISIONS.md plus the one-line dated ledger line in CLAUDE.md. Use the moment a decision is made.
---

# Record a decision

## Steps

1. Take the next free ID from `docs/DECISIONS.md` (`D-NNN`, never reused).
2. Append the entry in the template format:
   ```
   ### D-NNN: <title>

   - **Context:** <the situation and the sources that disagree, if any>
   - **Options considered:** <option — trade-off; option — trade-off>
   - **Decision:** <what, and who decided: owner | orchestrator (reversible) | proposed>
   - **Consequences:** <what follows, including what is now forbidden or required>
   - **With more time:** <the production path>
   ```
3. Append ONE line to the ledger in `CLAUDE.md` under "Decision ledger":
   `- YYYY-MM-DD — <one-line decision> ([D-NNN](docs/DECISIONS.md#d-nnn-<slug>))`
   No essays in the ledger.
4. A decision that supersedes another marks the old entry `Superseded by D-NNN` (both stay).
5. Owner decisions are marked as such; orchestrator decisions on reversible matters say
   "orchestrator, reversible" and appear in the next gate report.

## Output (fixed shape)

```
D-NNN: <title> — <decided by> — ledger line added
```
