"""User accounts: profiles, passwords and administration.

Role: re-exports `UserDetails`, `UserPage`, `UserService` and `build_user_service` as the
  feature's public surface.
Used by: `backend.api.dependencies.services`, `backend.api.v1.users.router`;
  tests/unit/backend/test_user_service.py.
Depends on: `backend.services.users.service`.
Key invariants: none.
"""

from backend.services.users.service import UserDetails, UserPage, UserService, build_user_service

__all__ = ["UserDetails", "UserPage", "UserService", "build_user_service"]
