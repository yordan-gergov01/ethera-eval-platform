"""Permission checks for endpoints.

Role: `require_permissions(...)`, the dependency through which an endpoint declares what it needs,
  never which role may call it:
    @router.get("/users", dependencies=[require_permissions(Permission.USERS_READ)])
Used by: `backend.api.v1.roles.router`, `backend.api.v1.users.router`.
Depends on: `CurrentUserDep` from `backend.api.dependencies.auth`, `common_lib.permissions`,
  `common_lib.errors.PermissionDeniedError`.
Key invariants: permissions are checked against the current user's role as stored in the
  database and loaded on every request, so a change of role applies immediately; endpoints never
  check role names (template_core D-006). `Security` (not `Depends`) is deliberate: it lists the
  permissions as scopes in the OpenAPI security requirement. 401 without a valid token, 403
  without the permissions; calling it with no permission is a programming error.
"""

from typing import Any

import structlog
from fastapi import Security

from backend.api.dependencies.auth import CurrentUserDep
from backend.services.auth import CurrentUser
from common_lib.errors import PermissionDeniedError
from common_lib.permissions import Permission

logger = structlog.get_logger(__name__)


def require_permissions(*required: Permission) -> Any:
    """A dependency that answers 401 without a valid token and 403 without the permissions."""
    if not required:
        raise ValueError("require_permissions needs at least one permission")

    async def check_permissions(user: CurrentUserDep) -> CurrentUser:
        missing = set(required) - user.permissions
        if missing:
            logger.warning("permission_denied", missing=sorted(missing))
            raise PermissionDeniedError()
        return user

    # Security (rather than Depends) lists the permissions as scopes in OpenAPI.
    return Security(check_permissions, scopes=[permission.value for permission in required])
