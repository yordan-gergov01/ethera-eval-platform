"""All `/api/v1` routes. A new feature adds its router here.

Role: builds `api_router` (core features under `/api/v1`) and `module_api_router`, which wraps a
  domain module's router the same way.
Used by: `backend.main` (mounts `api_router` and one `module_api_router` per `ModuleMount`).
Depends on: the auth, roles and users routers, `limit_requests`,
  `backend.api.errors.documented_problem`.
Key invariants: every `/api/v1` request — core or module — is rate limited before anything else
  runs and documents the same common errors; the core never names a domain module, it only wraps
  the routers it is given (D-003).
"""

from typing import Any

from fastapi import APIRouter, Depends

from backend.api.dependencies.rate_limit import limit_requests
from backend.api.errors import documented_problem
from backend.api.v1.auth.router import router as auth_router
from backend.api.v1.roles.router import router as roles_router
from backend.api.v1.users.router import router as users_router

# Documented on every route; the real bodies come from backend.api.errors.
COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    400: documented_problem("Malformed request"),
    413: documented_problem("Request body too large"),
    422: documented_problem("Validation failed"),
    429: documented_problem("Too many requests; see Retry-After"),
    500: documented_problem("Unexpected error"),
    503: documented_problem("The database or another dependency is temporarily unavailable"),
}

# Every /api/v1 request is rate limited before anything else runs.
api_router = APIRouter(
    prefix="/api/v1", responses=COMMON_ERRORS, dependencies=[Depends(limit_requests)]
)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)


def module_api_router(router: APIRouter) -> APIRouter:
    """Wrap a domain module's router so it is served under `/api/v1` like the core's own:
    rate limited before anything else runs, with the same documented errors."""
    wrapped = APIRouter(
        prefix="/api/v1", responses=COMMON_ERRORS, dependencies=[Depends(limit_requests)]
    )
    wrapped.include_router(router)
    return wrapped
