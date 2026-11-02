"""Migrations of the evaluation module's Tortoise app `evaluation` (tables `eval_*`).

Role: the evaluation module's own migrations package (D-007); module DDL only, never core DDL.
Used by: Tortoise's migration runner through `evals.evaluation.module` (`ModuleMount.migrations`).
Depends on: the core and registry migrations it names as dependencies.
Key invariants: revisions are generated, reviewed and never edited once applied.
"""
