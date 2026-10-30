"""The current user, resolved from the bearer token on every request.

Role: the `get_current_user` dependency and the `CurrentUserDep` alias protected routes use.
Used by: `backend.api.dependencies.permissions`, `backend.api.v1.auth.router`,
  `backend.api.v1.users.router`.
Depends on: `AuthService` (via `backend.api.dependencies.services`), FastAPI's
  `OAuth2PasswordBearer`, `common_lib.errors.AuthenticationError`.
Key invariants: `auto_error=False`, so a missing token is our own 401 problem details, not
  FastAPI's default body. The user is loaded from the database on every request (template_core
  D-006), so deactivation and logout apply to the next request. The user ID is bound to the log
  context so every later line of the request names the user.
"""

from typing import Annotated

import structlog
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from backend.api.dependencies.services import get_auth_service
from backend.services.auth import AuthService, CurrentUser
from common_lib.errors import AuthenticationError

LOGIN_PATH = "/api/v1/auth/login"

# auto_error=False: a missing token becomes our own problem details response
# rather than FastAPI's default body.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=LOGIN_PATH, auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> CurrentUser:
    """401 unless the request carries a valid token of an active user."""
    if token is None:
        raise AuthenticationError("Authentication is required.")
    user = await auth.authenticate(token)
    # Every later log line of this request, including the access line, names the user.
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
