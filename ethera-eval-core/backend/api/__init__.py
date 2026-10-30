"""HTTP layer of the backend. Never imports the ORM or the data access layer.

Role: package marker for the FastAPI routes, dependencies, error mapping and middleware.
Used by: `backend.main`, which mounts its routers, handlers and middleware.
Depends on: nothing itself; its modules lean on FastAPI and `backend.services`.
Key invariants: the API calls services only — import-linter forbids `backend.api` importing
  `backend.dal`, `common_lib.models` or `tortoise` ("The API layer never touches the database
  directly") and keeps the layers api -> services -> dal pointing downwards.
"""
