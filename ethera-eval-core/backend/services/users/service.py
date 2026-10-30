"""User accounts: self-service changes and administration by permission holders.

Role: `UserService` — own profile and password changes, and listing, reading, creating and
  updating accounts — and `build_user_service`.
Used by: `backend.services.users` (re-export), and through it `backend.api.v1.users.router`.
Depends on: `backend.dal.users` (behind the `UserStore` Protocol), the `PasswordHasher`
  Protocol, `CurrentUser` from `backend.services.auth`, the request schemas in
  `common_lib.schemas.users`, the password policy, `common_lib.errors`.
Key invariants: nobody changes their own role or active status, not even an administrator (403);
  a change that would leave no active account holding `users:update` is refused (409); accounts
  are never deleted (template_core D-007). A password change needs the current password, must
  meet the policy, and ends every session. Logs carry field names and IDs only, never the
  personal values.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict

from backend.dal.users import (
    EMAIL_TAKEN_MESSAGE,
    NewUser,
    UserChanges,
    UserRecord,
    UserRepository,
    duplicate_error,
)
from backend.services.auth import CurrentUser
from backend.services.protocols import PasswordHasher
from common_lib.errors import (
    BusinessRuleError,
    ConflictError,
    ErrorCode,
    NotFoundError,
    PermissionDeniedError,
)
from common_lib.permissions import Permission
from common_lib.schemas.password import WeakPasswordError, validate_password
from common_lib.schemas.users import PasswordChange, UserAdminUpdate, UserCreate, UserSelfUpdate

logger = structlog.get_logger(__name__)

# Losing the last active holder of this permission would leave nobody able to
# manage accounts, and therefore nobody able to fix it.
PROTECTED_PERMISSION = Permission.USERS_UPDATE


class UserStore(Protocol):
    async def get_password_hash(self, user_id: UUID) -> str | None: ...

    async def email_in_use(self, email: str, *, except_user_id: UUID) -> bool: ...

    async def taken_identifiers(self, *, username: str, email: str) -> frozenset[str]: ...

    async def get_user(self, user_id: UUID) -> UserRecord | None: ...

    async def list_users(self, *, limit: int, offset: int) -> list[UserRecord]: ...

    async def count_users(self) -> int: ...

    async def create(self, user: NewUser) -> UUID: ...

    async def update_user(
        self, user_id: UUID, changes: UserChanges, *, keep_active_holder_of: str | None = None
    ) -> bool: ...

    async def replace_password(self, user_id: UUID, password_hash: str) -> None: ...


class UserDetails(BaseModel):
    """An account as administrators see it."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserPage(BaseModel):
    """One page of accounts and the total number of accounts."""

    items: list[UserDetails]
    total: int
    limit: int
    offset: int


class UserService:
    def __init__(self, users: UserStore, hasher: PasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    # Self-service

    async def update_own_profile(self, user: CurrentUser, changes: UserSelfUpdate) -> CurrentUser:
        """Change the caller's full name or email; the schema allows nothing else."""
        await self._ensure_email_free(changes.email, user.id)
        await self._users.update_user(
            user.id, UserChanges(full_name=changes.full_name, email=changes.email)
        )
        updated = changes.model_dump(exclude_unset=True)
        # Field names only: the values are personal data.
        logger.info("user_updated", target_user_id=str(user.id), fields=sorted(updated))
        return user.model_copy(update=updated)

    async def change_own_password(self, user: CurrentUser, change: PasswordChange) -> None:
        """Replace the caller's password and end every session, this one included.

        The current password is required, so a stolen token alone cannot take
        over the account.
        """
        password_hash = await self._users.get_password_hash(user.id)
        if password_hash is None:
            # Authenticated a moment ago; the account cannot have disappeared, as
            # users are never deleted.
            raise NotFoundError()
        check = await self._hasher.verify(change.current_password.get_secret_value(), password_hash)
        if not check.valid:
            logger.warning("password_change_failed", reason="wrong_current_password")
            raise BusinessRuleError(
                "The current password is incorrect.", code=ErrorCode.INVALID_CURRENT_PASSWORD
            )

        new_password = change.new_password.get_secret_value()
        _check_password_policy(new_password, username=user.username, email=user.email)
        await self._users.replace_password(user.id, await self._hasher.hash(new_password))
        logger.info("password_changed", target_user_id=str(user.id))

    # Administration

    async def list_users(self, *, limit: int, offset: int) -> UserPage:
        records = await self._users.list_users(limit=limit, offset=offset)
        return UserPage(
            items=[_details(record) for record in records],
            total=await self._users.count_users(),
            limit=limit,
            offset=offset,
        )

    async def get_user(self, user_id: UUID) -> UserDetails:
        return _details(await self._get_record(user_id))

    async def create_user(self, new: UserCreate) -> UserDetails:
        """Create an account with the given role; the password must meet the policy."""
        password = new.password.get_secret_value()
        _check_password_policy(password, username=new.username, email=new.email)
        taken = await self._users.taken_identifiers(username=new.username, email=new.email)
        if taken:
            raise duplicate_error(taken)

        user_id = await self._users.create(
            NewUser(
                username=new.username,
                email=new.email,
                full_name=new.full_name,
                password_hash=await self._hasher.hash(password),
                role_name=new.role.value,
            )
        )
        logger.info("user_created", target_user_id=str(user_id), role=new.role.value)
        return await self.get_user(user_id)

    async def update_user(
        self, actor: CurrentUser, user_id: UUID, changes: UserAdminUpdate
    ) -> UserDetails:
        """Change another account's profile, role or active status.

        Nobody changes their own role or active status, not even an administrator,
        and the last active account able to manage accounts cannot lose that ability.
        """
        target = await self._get_record(user_id)
        role_changes = changes.role is not None and changes.role.value != target.role
        status_changes = changes.is_active is not None and changes.is_active != target.is_active
        if actor.id == user_id and (role_changes or status_changes):
            logger.warning("self_modification_denied", target_user_id=str(user_id))
            raise PermissionDeniedError(
                "You cannot change your own role or active status.",
                code=ErrorCode.SELF_MODIFICATION_FORBIDDEN,
            )
        await self._ensure_email_free(changes.email, user_id)

        applied = await self._users.update_user(
            user_id,
            UserChanges(
                full_name=changes.full_name,
                email=changes.email,
                role_name=None if changes.role is None else changes.role.value,
                is_active=changes.is_active,
            ),
            # Only a role change or a deactivation can take the permission away.
            keep_active_holder_of=PROTECTED_PERMISSION.value
            if role_changes or (status_changes and not changes.is_active)
            else None,
        )
        if not applied:
            logger.warning("last_admin_protected", target_user_id=str(user_id))
            raise ConflictError(
                f"At least one active account must keep the {PROTECTED_PERMISSION} permission.",
                code=ErrorCode.LAST_ADMIN_PROTECTED,
            )

        logger.info(
            "user_updated",
            target_user_id=str(user_id),
            fields=sorted(changes.model_dump(exclude_unset=True)),
        )
        if status_changes:
            event = "user_reactivated" if changes.is_active else "user_deactivated"
            logger.info(event, target_user_id=str(user_id))
        return await self.get_user(user_id)

    # Helpers

    async def _get_record(self, user_id: UUID) -> UserRecord:
        record = await self._users.get_user(user_id)
        if record is None:
            raise NotFoundError("The user does not exist.", code=ErrorCode.USER_NOT_FOUND)
        return record

    async def _ensure_email_free(self, email: str | None, user_id: UUID) -> None:
        if email is not None and await self._users.email_in_use(email, except_user_id=user_id):
            raise ConflictError(EMAIL_TAKEN_MESSAGE, code=ErrorCode.EMAIL_TAKEN)


def _check_password_policy(password: str, *, username: str, email: str) -> None:
    try:
        validate_password(password, username=username, email=email)
    except WeakPasswordError as exc:
        raise BusinessRuleError(str(exc), code=ErrorCode.WEAK_PASSWORD) from exc


def _details(record: UserRecord) -> UserDetails:
    return UserDetails(
        id=record.id,
        username=record.username,
        email=record.email,
        full_name=record.full_name,
        role=record.role,
        is_active=record.is_active,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def build_user_service(hasher: PasswordHasher) -> UserService:
    """Wire the service to the real repository."""
    return UserService(users=UserRepository(), hasher=hasher)
