"""Authentication: login, logout and the current user.

Role: re-exports `AuthService`, `CurrentUser` and `build_auth_service` as the feature's public
  surface.
Used by: `backend.api.dependencies` (auth, permissions, services), the auth and users routers,
  `backend.services.users.service`.
Depends on: `backend.services.auth.service`.
Key invariants: covered by the 100% auth coverage gate (D-008).
"""

from backend.services.auth.service import AuthService, CurrentUser, build_auth_service

__all__ = ["AuthService", "CurrentUser", "build_auth_service"]
