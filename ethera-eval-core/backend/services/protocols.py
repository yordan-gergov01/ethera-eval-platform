"""Interfaces the services depend on, implemented in `backend.core` or `backend.dal`.

Role: the `PasswordHasher` Protocol, so services depend on an interface rather than on Argon2.
Used by: `backend.services.auth.service`, `backend.services.seeding.service`,
  `backend.services.users.service`.
Depends on: `backend.core.security.PasswordCheck` (the result type).
Key invariants: services stay testable with fakes; `backend.core.security.Argon2PasswordHasher`
  satisfies the Protocol structurally, without inheriting from it.
"""

from typing import Protocol

from backend.core.security import PasswordCheck


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...

    async def verify(self, password: str, password_hash: str) -> PasswordCheck: ...

    async def verify_dummy(self, password: str) -> None: ...
