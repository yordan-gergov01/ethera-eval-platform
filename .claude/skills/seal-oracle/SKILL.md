---
name: seal-oracle
description: Review a test-author's oracle for soundness, record the expected-failure map and SHA-256 hashes, and prepare (not make) the seal commit for the owner's approval (Bible Phases 3–4).
---

# Seal the oracle

Input: the test files written by the `test-author` agent for `specs/<slice>/contract.md`,
and its expected-failure map.

## Steps

1. **Soundness only** (not coverage taste):
   - zero imports of `backend.*`, `evals.*`, `runner.*`, `demo_target.*` internals — only
     public surfaces (HTTP via the ASGI client, broker, CLI, files) and test fixtures;
   - re-run every file yourself: each test fails **for the expected reason** (e.g. 404 for a
     missing route), never with an import, fixture or collection error;
   - anti-vacuity: no test can pass against the missing feature (a contracted 404 first proves
     a 200 on the caller's own resource);
   - lint/format clean.
   Unsound tests go back to the test author with the evidence; you never fix them yourself.
2. Write `specs/<slice>/SEALED.md`:
   - the list of sealed files with `sha256sum` of each;
   - the expected-failure map (test → how it fails today), from YOUR run;
   - the underdetermined cases the author listed as not sealed.
3. Add each sealed path to `permissions.deny` in `.claude/settings.json` as
   `Edit(/<path>)`.
4. Prepare the commit (do NOT run it): files = the sealed tests + `SEALED.md` + settings
   change; message:
   `test(<slice>): sealed oracle, written BEFORE the implementation; the implementation may
   not modify these files.`
   Ask the owner for the local commit (C3). Red tests are never pushed.

## Output (fixed shape)

```
| Sealed file | sha256 | Tests | Fail reason today |
Unsound tests returned: <n> (list)
Not sealed (underdetermined): <list>
Commit prepared: <message> — awaiting owner instruction
```
