"""`/api/v1/roles` routes.

Role: `GET /api/v1/roles` — every role with the permissions it grants, for choosing a role for
  an account.
Used by: `backend.api.v1.router` (included in `api_router`).
Depends on: `RoleService` (via `backend.api.dependencies.services`), `require_permissions`,
  `common_lib.permissions.Permission`.
Key invariants: read-only — roles are defined in code and synced at startup, so there is no
  endpoint to create or change them (template_core D-006); reading needs `users:read`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.dependencies.permissions import require_permissions
from backend.api.dependencies.services import get_role_service
from backend.api.errors import documented_problem
from backend.services.roles import RoleDetails, RoleService
from common_lib.permissions import Permission

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get(
    "",
    response_model=list[RoleDetails],
    dependencies=[require_permissions(Permission.USERS_READ)],
    responses={
        status.HTTP_401_UNAUTHORIZED: documented_problem("Missing or invalid token"),
        status.HTTP_403_FORBIDDEN: documented_problem("Missing permission"),
    },
)
async def list_roles(roles: Annotated[RoleService, Depends(get_role_service)]) -> list[RoleDetails]:
    """Every role with the permissions it grants, for choosing a role for an account."""
    return await roles.list_roles()
