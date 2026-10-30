"""Business logic of the backend. Knows nothing about HTTP.

Role: package marker for the services (auth, health, rate_limit, roles, seeding, users) and the
  Protocols they depend on.
Used by: `backend.api` (via `backend.api.dependencies` and the routers) and `backend.main`.
Depends on: nothing itself; its services use `backend.dal`, `backend.core` and `common_lib`.
Key invariants: import-linter forbids services importing `backend.messaging`, `backend.api`,
  `aio_pika` or `fastapi` ("Services never import the broker, messaging or HTTP code"); services
  raise errors by meaning (`common_lib.errors`), never HTTP statuses (template_core D-005).
"""
