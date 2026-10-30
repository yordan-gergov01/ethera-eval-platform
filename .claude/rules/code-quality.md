# Code quality

Source: Bible Part III "Code quality" and "The language boundary", plus template tooling
(`docs/reference/TEMPLATE_CONVENTIONS.md`).

## Every file opens with a header

Python: the module docstring. TypeScript (`src/`, except generated `schema.gen.ts`): a leading
`/** ... */` block. Four labelled parts, in this order:

```
"""One-line summary.

Role: what this file is for.
Used by: who imports or calls it.
Depends on: what it leans on.
Key invariants: deliberate behaviour the next agent must not "fix"; `none` only if truly none.
"""
```

- A header that contradicts the code is a defect.
- Every `test_*` name mentioned in a header must resolve to a real test function.

## Size

- Files: target 200–400 lines, hard cap 600. Functions: target 30–50 lines, cap 100.
  Nesting ≤ 3; prefer early returns. Existing offenders are pinned by a ratchet that refuses
  growth and new offenders.

## Types and errors

- Types on every signature. mypy strict, TypeScript strict. No `Any` without a justifying
  comment on the same line.
- Custom exception classes with descriptive names; services raise by meaning
  (`common_lib.errors`); one module maps errors to RFC 9457 problem details. Never expose
  internals in user-facing messages.

## Naming and language

- Code speaks English: identifiers, docstrings, comments, test names.
- Use the ubiquitous language of `docs/domain/glossary.md` exactly; its forbidden synonyms
  never appear in identifiers.
- CRUD naming: `create_`, `get_`, `list_`, `update_`, `delete_`.
- Every machine value shown to users goes through a label map typed `Record<Value, Label>`.

## Comments

Only for security-critical logic, non-obvious business rules, argued workarounds and measured
performance decisions. Never "what the next line does", never review notes, never TODOs
without a slice reference.

## Dependencies

Nothing added that the templates and the Bible do not use without a `D-NNN` decision. Python:
add to `requirements/<service>.in`, recompile with `uv pip compile --universal
--generate-hashes --python-version 3.12` in order backend → runner → dev. Web: exact versions,
`npm ci`.

## Mechanical checks

- `ruff format --check .`, `ruff check .`, `mypy` (strict), `npm run check`.
- `tests/architecture/test_docstring_headers.py` — header present with four parts in every
  Python source file; `test_*` references resolve.
- `tests/architecture/test_file_length.py` — file cap 600 and function cap 100, with the
  pinned-offender ratchet.
- `ethera-eval-web/src/test/file-headers.test.ts` — header present in every `src/` TS file.
