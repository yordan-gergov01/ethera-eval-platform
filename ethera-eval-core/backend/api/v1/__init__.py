"""Version 1 of the HTTP API, one package per feature.

Role: package marker for the `/api/v1` routers (auth, roles, users) and their aggregator.
Used by: `backend.main` imports `backend.api.v1.router`.
Depends on: nothing itself.
Key invariants: none.
"""
