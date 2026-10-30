"""Data access layer: every database query of the backend lives here.

Role: package marker for the repositories (health, rate_limit, roles, users).
Used by: `backend.services` imports the feature packages below it.
Depends on: nothing itself; its repositories use Tortoise and `common_lib.models`.
Key invariants: the lowest backend layer — import-linter keeps api -> services -> dal pointing
  downwards and forbids the API from importing this package directly.
"""
