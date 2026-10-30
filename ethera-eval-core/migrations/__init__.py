"""Versioned database migrations, applied by the backend at startup.

Role: the core app's (`models`) migrations package for Tortoise's built-in migrations.
Used by: `backend.core.database` (`MIGRATIONS_MODULE`), and through it `backend.core.startup`
  (applied at startup) and `evals.migration_cli` (the `tortoise` command line).
Depends on: nothing itself.
Key invariants: holds core DDL only; each domain module has its own migrations package, so no
  revision mixes core and module DDL (D-007). Migrations are generated, reviewed and committed,
  and applied at startup under the advisory lock, each in its own transaction (template_core
  D-004). An applied migration is never edited; a change is a new revision.
"""
