"""Service wiring for request handlers.

Role: builds the services a request handler needs. Long-lived components (password hasher,
  token service) are created once per process by the application factory and kept on
  `app.state`; services are cheap and built per request.
Used by: `backend.api.dependencies.auth`, `backend.api.dependencies.rate_limit`, and the
  routers in `backend.api.v1` (auth, roles, users).
Depends on: the `build_*` factories of `backend.services` (auth, rate_limit, roles, users);
  `app.state.password_hasher` and `app.state.token_service` set by `backend.main`.
Key invariants: no per-process state is created here; the API never constructs repositories
  (the services' factories do).
"""

from fastapi import Request

from backend.services.auth import AuthService, build_auth_service
from backend.services.rate_limit import RateLimiter, build_rate_limiter
from backend.services.roles import RoleService, build_role_service
from backend.services.users import UserService, build_user_service


def get_auth_service(request: Request) -> AuthService:
    state = request.app.state
    return build_auth_service(state.password_hasher, state.token_service)


def get_user_service(request: Request) -> UserService:
    return build_user_service(request.app.state.password_hasher)


def get_role_service() -> RoleService:
    return build_role_service()


def get_rate_limiter() -> RateLimiter:
    return build_rate_limiter()
