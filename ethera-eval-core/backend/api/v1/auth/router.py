"""`POST /api/v1/auth/login` and `POST /api/v1/auth/logout`.

Role: exchanges a username and password (OAuth2 form data) for an access token, and revokes
  every access token of the current user.
Used by: `backend.api.v1.router` (included in `api_router`).
Depends on: `AuthService` (via `backend.api.dependencies.services`), `CurrentUserDep`,
  `limit_login_attempts`, `backend.api.errors.documented_problem`.
Key invariants: login is form data (OAuth2 password flow) and counts against the stricter login
  rate limit as well as the default one (template_core D-008). Logout revokes tokens on every
  device by incrementing the token version (template_core D-006); there are no refresh tokens.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from backend.api.dependencies.auth import CurrentUserDep
from backend.api.dependencies.rate_limit import limit_login_attempts
from backend.api.dependencies.services import get_auth_service
from backend.api.errors import documented_problem
from backend.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: documented_problem("Missing or invalid credentials")
}


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - the OAuth2 token type, not a secret
    expires_in: int


@router.post(
    "/login",
    response_model=TokenResponse,
    responses=UNAUTHORIZED,
    dependencies=[Depends(limit_login_attempts)],
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Exchange a username and password (form data) for an access token."""
    token = await auth.login(form.username, form.password)
    return TokenResponse(access_token=token.token, expires_in=token.expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=UNAUTHORIZED)
async def logout(
    user: CurrentUserDep,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    """Revoke every access token of the current user, on every device."""
    await auth.logout(user)
