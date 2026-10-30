"""FastAPI dependencies: the current user, permission checks and service wiring.

Role: package marker grouping the per-request dependencies the routers declare.
Used by: the routers in `backend.api.v1` import its submodules directly.
Depends on: nothing itself.
Key invariants: none.
"""
