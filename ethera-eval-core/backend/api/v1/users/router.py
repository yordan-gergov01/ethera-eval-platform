"""`/api/v1/users` routes.

Role: self-service (`/users/me`: profile, own name/email, own password) and account
  administration (list, create, read, update) over HTTP.
Used by: `backend.api.v1.router` (included in `api_router`).
Depends on: `UserService` (via `backend.api.dependencies.services`), `CurrentUserDep`,
  `require_permissions`, the request schemas in `common_lib.schemas.users`.
Key invariants: no delete endpoint — accounts are deactivated, never deleted; nobody changes
  their own role or active status (403); a change that would leave no active holder of
  `users:update` is a 409 (template_core D-007). `/me` exposes the permissions so the frontend
  shows only what the user may use; the backend still checks. A password change ends every
  session. Each operation has its own request schema, so `/me` cannot send a role.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel

from backend.api.dependencies.auth import CurrentUserDep
from backend.api.dependencies.permissions import require_permissions
from backend.api.dependencies.services import get_user_service
from backend.api.errors import documented_problem
from backend.services.auth import CurrentUser
from backend.services.users import UserDetails, UserPage, UserService
from common_lib.permissions import Permission
from common_lib.schemas.users import PasswordChange, UserAdminUpdate, UserCreate, UserSelfUpdate

router = APIRouter(prefix="/users", tags=["users"])

UserServiceDep = Annotated[UserService, Depends(get_user_service)]

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: documented_problem("Missing or invalid token")
}
FORBIDDEN: dict[int | str, dict[str, Any]] = UNAUTHORIZED | {
    status.HTTP_403_FORBIDDEN: documented_problem("Missing permission")
}
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: documented_problem("The user does not exist")
}


class CurrentUserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: str
    role: str
    # The frontend shows only what the user may use; the backend still checks.
    permissions: list[Permission]

    @classmethod
    def of(cls, user: CurrentUser) -> "CurrentUserResponse":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            permissions=sorted(user.permissions),
        )


@router.get("/me", response_model=CurrentUserResponse, responses=UNAUTHORIZED)
async def read_current_user(user: CurrentUserDep) -> CurrentUserResponse:
    """The current user's profile, role and permissions."""
    return CurrentUserResponse.of(user)


@router.patch(
    "/me",
    response_model=CurrentUserResponse,
    responses=UNAUTHORIZED
    | {status.HTTP_409_CONFLICT: documented_problem("The email address is already in use")},
)
async def update_current_user(
    changes: UserSelfUpdate, user: CurrentUserDep, users: UserServiceDep
) -> CurrentUserResponse:
    """Change your own full name or email. Role and active status cannot be sent here."""
    return CurrentUserResponse.of(await users.update_own_profile(user, changes))


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT, responses=UNAUTHORIZED)
async def change_current_user_password(
    change: PasswordChange, user: CurrentUserDep, users: UserServiceDep
) -> None:
    """Change your own password. Every session ends, so log in again afterwards.

    A wrong current password or a new password that breaks the policy is a 422.
    """
    await users.change_own_password(user, change)


# Administration


@router.get(
    "",
    response_model=UserPage,
    dependencies=[require_permissions(Permission.USERS_READ)],
    responses=FORBIDDEN,
)
async def list_users(
    users: UserServiceDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserPage:
    """All accounts, oldest first, one page at a time."""
    return await users.list_users(limit=limit, offset=offset)


@router.post(
    "",
    response_model=UserDetails,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_permissions(Permission.USERS_CREATE)],
    responses=FORBIDDEN
    | {status.HTTP_409_CONFLICT: documented_problem("The username or email is already in use")},
)
async def create_user(
    new: UserCreate, users: UserServiceDep, request: Request, response: Response
) -> UserDetails:
    """Create an account with a role. A password that breaks the policy is a 422."""
    created = await users.create_user(new)
    response.headers["Location"] = request.app.url_path_for("read_user", user_id=str(created.id))
    return created


@router.get(
    "/{user_id}",
    response_model=UserDetails,
    dependencies=[require_permissions(Permission.USERS_READ)],
    responses=FORBIDDEN | NOT_FOUND,
)
async def read_user(user_id: UUID, users: UserServiceDep) -> UserDetails:
    """One account."""
    return await users.get_user(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserDetails,
    responses=FORBIDDEN
    | NOT_FOUND
    | {
        status.HTTP_409_CONFLICT: documented_problem(
            "The email is already in use, or the change would leave no active account "
            "able to manage accounts"
        )
    },
)
async def update_user(
    user_id: UUID,
    changes: UserAdminUpdate,
    users: UserServiceDep,
    actor: Annotated[CurrentUser, require_permissions(Permission.USERS_UPDATE)],
) -> UserDetails:
    """Change an account's name, email, role or active status.

    Your own role and active status cannot be changed (403); use `/users/me` for
    your own name and email, or this endpoint with your own ID.
    """
    return await users.update_user(actor, user_id, changes)
