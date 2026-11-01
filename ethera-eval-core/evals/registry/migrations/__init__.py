"""Migrations of the registry's Tortoise app `registry` (tables `reg_*`).

Role: the registry's own migrations package (D-007); module DDL only, never core DDL.
Used by: Tortoise's migration runner through `evals.registry.module` (`ModuleMount.migrations`).
Depends on: the core migrations it names as dependencies.
Key invariants: revisions are generated, reviewed and never edited once applied.
"""
