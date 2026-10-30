"""Bring the database in line with the code at startup: permissions, roles, admin.

Role: `SeedingService.seed` syncs `DEFAULT_ROLE_GRANTS` into the database and creates the admin
  account if it does not exist; `build_seeding_service` wires the real repositories.
Used by: `backend.services.seeding` (re-export), and through it `backend.main`.
Depends on: `backend.dal.roles`, `backend.dal.users`, the `PasswordHasher` Protocol,
  `common_lib.permissions` (`DEFAULT_ROLE_GRANTS`, `RoleName`).
Key invariants: idempotent, safe to run on every start by every replica (under the startup
  lock). Permissions are defined in code and synced at startup (template_core D-006). The admin
  account is create-only: an existing one is never touched, so a password changed after the
  first start is not reset by a restart.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

import structlog
from pydantic import SecretStr

from backend.dal.roles import RoleRepository
from backend.dal.users import NewUser, UserRepository
from backend.services.protocols import PasswordHasher
from common_lib.permissions import DEFAULT_ROLE_GRANTS, RoleName

logger = structlog.get_logger(__name__)


class GrantStore(Protocol):
    async def sync_grants(self, grants: Mapping[str, Iterable[str]]) -> None: ...


class AccountStore(Protocol):
    async def exists(self, *, username: str, email: str) -> bool: ...

    async def create(self, user: NewUser) -> object: ...


@dataclass(frozen=True, slots=True)
class AdminAccount:
    username: str
    email: str
    password: SecretStr


class SeedingService:
    """Idempotent: safe to run on every start, by every replica (under the startup lock)."""

    def __init__(
        self,
        grants: GrantStore,
        accounts: AccountStore,
        hasher: PasswordHasher,
    ) -> None:
        self._grants = grants
        self._accounts = accounts
        self._hasher = hasher

    async def seed(self, admin: AdminAccount) -> None:
        await self._grants.sync_grants(
            {role.value: [p.value for p in grants] for role, grants in DEFAULT_ROLE_GRANTS.items()}
        )
        logger.info("permissions_synced", roles=len(DEFAULT_ROLE_GRANTS))

        # Create-only: an existing admin is never touched, so a password changed after
        # the first start is not reset by a restart.
        if await self._accounts.exists(username=admin.username, email=admin.email):
            logger.info("admin_account_exists", username=admin.username)
            return
        await self._accounts.create(
            NewUser(
                username=admin.username,
                email=admin.email,
                full_name="Administrator",
                password_hash=await self._hasher.hash(admin.password.get_secret_value()),
                role_name=RoleName.ADMIN.value,
            )
        )
        logger.info("admin_account_created", username=admin.username)


def build_seeding_service(hasher: PasswordHasher) -> SeedingService:
    """Wire the service to the real repositories."""
    return SeedingService(
        grants=RoleRepository(),
        accounts=UserRepository(),
        hasher=hasher,
    )
