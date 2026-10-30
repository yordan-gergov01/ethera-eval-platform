---
name: add-module
description: Create a new domain module in ethera-eval-core/evals across all layers with its barrel, MODULES.py line, import contracts, table prefix, migration folder, mirrored web feature, and glossary/carrier entries. Use at the start of the slice that introduces the module.
---

# Add a domain module

Inputs: module name (one of the bounded contexts in `docs/domain/context-map.md`; a new one
needs an owner decision first), its table prefix, its permissions.

## Steps

1. **Backend package** `ethera-eval-core/evals/<module>/`:
   `__init__.py` (barrel: explicit re-exports + `__all__`), `api/`, `services/`,
   `repositories/`, `domain/`, `migrations/`, `models.py` (Tortoise models, tables prefixed
   `<prefix>_`). Every file opens with the Role / Used by / Depends on / Key invariants header.
2. **Mount**: append ONE entry to `evals/MODULES.py` (router, consumers, periodic tasks, the
   module's Tortoise app label and migrations package). Never edit existing entries.
3. **Tortoise app**: one app label per module with its own `migrations` package, as recorded
   in `docs/DECISIONS.md` (multi-app migrations decision). The first migration creates only
   this module's tables; core DDL never appears in it.
4. **Import contracts** in `ethera-eval-core/pyproject.toml` (append):
   - layers `evals.<module>.api → services → repositories → domain`;
   - `evals.<module>.domain` forbidden: `tortoise`, `fastapi`, `aio_pika`, `httpx`,
     `structlog`, `logging`, `backend`;
   - cross-module imports only through `evals.<other>` barrels, only along the context map.
5. **Permissions / error codes / audit actions**: append members to the core registries;
   the completeness test must pass.
6. **Web feature** `ethera-eval-web/src/features/<module-kebab>/` (`api.ts`, hooks,
   components), its page(s) in `src/pages/`, ONE entry per page in `PROTECTED_PAGES`, the
   feature name appended to `FEATURES` in `eslint.config.js`, label maps typed
   `Record<Value, Label>`.
7. **Docs**: glossary terms (accepted only), carrier `docs/domain/carriers/<module>.md`,
   context-map edge(s).
8. **Tests**: mirrored test folders; the boot-without-`evals` test and import-contract test
   still pass.

## Output (fixed shape)

```
Module: <name>  prefix: <prefix>_  app label: <label>
Files created: <tree>
Registries appended: MODULES.py, pyproject contracts (<n>), permissions (<list>), FEATURES, PROTECTED_PAGES
Checks: lint-imports <n kept>, mypy ✓, boot-without-evals ✓, npm run check ✓
```
