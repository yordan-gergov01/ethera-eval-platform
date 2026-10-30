"""Password hashing with Argon2id.

Role: `Argon2PasswordHasher` (hash, verify with upgrade, dummy verification) and the
  `PasswordCheck` result.
Used by: `backend.main` (one hasher per process on `app.state`); `backend.services.protocols`
  (the `PasswordCheck` type behind the `PasswordHasher` Protocol).
Depends on: pwdlib's Argon2 hasher, `common_lib.schemas.password.normalize_password`.
Key invariants: hashing is deliberately slow and CPU-bound, so it runs in a worker thread and
  never blocks the event loop. Passwords are normalised to NFKC exactly as the password policy
  does before they are hashed or verified. A hash with outdated parameters is upgraded on a
  valid login (template_core D-006). `verify_dummy` keeps unknown-username logins as slow as
  wrong-password ones, so usernames cannot be enumerated by timing. Covered by the 100%
  auth coverage gate (D-008).
"""

import asyncio
from dataclasses import dataclass

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from common_lib.schemas.password import normalize_password


@dataclass(frozen=True, slots=True)
class PasswordCheck:
    """Result of verifying a password against a stored hash."""

    valid: bool
    # A fresh hash when the stored one uses outdated parameters; store it.
    upgraded_hash: str | None = None


class Argon2PasswordHasher:
    """Argon2id via pwdlib, with the library's recommended parameters."""

    def __init__(self, hasher: Argon2Hasher | None = None) -> None:
        self._hash = PasswordHash((hasher or Argon2Hasher(),))
        self._dummy_hash: str | None = None

    async def hash(self, password: str) -> str:
        """Hash a new password."""
        return await asyncio.to_thread(self._hash.hash, normalize_password(password))

    async def verify(self, password: str, password_hash: str) -> PasswordCheck:
        """Verify a password; also returns an upgraded hash if the parameters changed."""
        valid, upgraded = await asyncio.to_thread(
            self._hash.verify_and_update, normalize_password(password), password_hash
        )
        return PasswordCheck(valid=valid, upgraded_hash=upgraded if valid else None)

    async def verify_dummy(self, password: str) -> None:
        """Spend the same time as a real verification, for a user that does not exist.

        Without it, a login for an unknown username would answer measurably faster
        than one with a wrong password, revealing which usernames exist.
        """
        if self._dummy_hash is None:
            self._dummy_hash = await self.hash("not-a-real-password-only-for-timing")
        await self.verify(password, self._dummy_hash)
