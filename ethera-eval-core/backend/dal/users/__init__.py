"""Data access for user accounts.

Role: re-exports the user repository, its value types and the duplicate-account helpers as the
  feature's public surface.
Used by: `backend.services.auth.service`, `backend.services.seeding.service`,
  `backend.services.users.service`; the user service and admin tests.
Depends on: `backend.dal.users.repository`.
Key invariants: none.
"""

from backend.dal.users.repository import (
    EMAIL_TAKEN_MESSAGE,
    Credentials,
    NewUser,
    UserChanges,
    UserProfile,
    UserRecord,
    UserRepository,
    duplicate_error,
)

__all__ = [
    "EMAIL_TAKEN_MESSAGE",
    "Credentials",
    "NewUser",
    "UserChanges",
    "UserProfile",
    "UserRecord",
    "UserRepository",
    "duplicate_error",
]
