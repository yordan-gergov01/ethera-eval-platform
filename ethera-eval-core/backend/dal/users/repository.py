"""User accounts.

Role: `UserRepository`, every query on user accounts — create, credentials, profile with role and
  permissions, admin listing, guarded updates, password replacement and token revocation — and
  the plain value types it returns.
Used by: `backend.dal.users` (re-export), and through it `backend.services.auth.service`,
  `backend.services.seeding.service`, `backend.services.users.service`;
  tests/integration/test_users_admin.py imports it directly.
Depends on: Tortoise (queries, `F`, `Q`, transactions), `common_lib.models` (`User`, `Role`),
  `common_lib.errors` (`ConflictError`, `ErrorCode`).
Key invariants: there is no delete — accounts are deactivated, never deleted (template_core
  D-007). A guarded update (`keep_active_holder_of`) takes a transaction-scoped advisory lock and
  rolls back if no active account would still hold the permission, so two administrators
  demoting each other at once cannot both succeed. Unique violations from a concurrent request
  become the same 409 the service raises after its own check. Bulk updates set `updated_at`
  explicitly (they skip auto_now). The password change and logout bump `token_version` in the
  database, atomically. `Credentials` never leave the service layer. The advisory lock ID
  differs from the startup lock's.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import IntegrityError
from tortoise.expressions import F, Q
from tortoise.transactions import in_transaction

from common_lib.errors import ConflictError, ErrorCode
from common_lib.models import Role, User

USERNAME_TAKEN_MESSAGE = "This username is already in use."
EMAIL_TAKEN_MESSAGE = "This email address is already in use."

# Identifies "guarded account changes" among PostgreSQL advisory locks; distinct from
# the startup lock. Not a secret.
ACCOUNT_GUARD_LOCK_ID = 7_420_150_268_313_725_002


@dataclass(frozen=True, slots=True)
class NewUser:
    username: str
    email: str
    full_name: str
    password_hash: str
    role_name: str


@dataclass(frozen=True, slots=True)
class Credentials:
    """What login needs: never leaves the service layer."""

    user_id: UUID
    password_hash: str
    is_active: bool
    token_version: int


@dataclass(frozen=True, slots=True)
class UserProfile:
    """A user with the role and the permissions it currently holds."""

    id: UUID
    username: str
    email: str
    full_name: str
    is_active: bool
    token_version: int
    role: str
    permissions: frozenset[str]


@dataclass(frozen=True, slots=True)
class UserRecord:
    """An account as administrators see it."""

    id: UUID
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class UserChanges:
    """Fields to change on an account; `None` keeps a field unchanged."""

    full_name: str | None = None
    email: str | None = None
    role_name: str | None = None
    is_active: bool | None = None


def duplicate_error(taken: frozenset[str]) -> ConflictError:
    """The conflict for an account whose username or email is already in use."""
    if "username" in taken:
        return ConflictError(USERNAME_TAKEN_MESSAGE, code=ErrorCode.USERNAME_TAKEN)
    return ConflictError(EMAIL_TAKEN_MESSAGE, code=ErrorCode.EMAIL_TAKEN)


class UserRepository:
    """Every query on user accounts."""

    async def exists(self, *, username: str, email: str) -> bool:
        """Whether an account already uses this username or this email."""
        return await User.filter(Q(username=username) | Q(email=email)).exists()

    async def create(self, user: NewUser) -> UUID:
        """Create an account with the given role and return its ID."""
        role = await Role.get(name=user.role_name)
        try:
            created = await User.create(
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                password_hash=user.password_hash,
                role=role,
            )
        except IntegrityError as exc:
            # The service checks first; this covers a concurrent request creating the
            # same account in between. The winner is committed, so a lookup tells which.
            taken = await self.taken_identifiers(username=user.username, email=user.email)
            raise duplicate_error(taken) from exc
        return created.id

    async def get_credentials(self, username: str) -> Credentials | None:
        """Look up the stored credentials of a (normalised) username."""
        user = await User.get_or_none(username=username)
        if user is None:
            return None
        return Credentials(
            user_id=user.id,
            password_hash=user.password_hash,
            is_active=user.is_active,
            token_version=user.token_version,
        )

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        """Load a user with role and permissions in two queries."""
        user = await User.get_or_none(id=user_id).prefetch_related("role__permissions")
        if user is None:
            return None
        role: Role = user.role
        return UserProfile(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            token_version=user.token_version,
            role=role.name,
            permissions=frozenset(p.code for p in role.permissions),
        )

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        await User.filter(id=user_id).update(
            password_hash=password_hash, updated_at=datetime.now(UTC)
        )

    async def get_password_hash(self, user_id: UUID) -> str | None:
        user = await User.get_or_none(id=user_id).only("id", "password_hash")
        return None if user is None else user.password_hash

    async def email_in_use(self, email: str, *, except_user_id: UUID) -> bool:
        """Whether another account already uses this (normalised) email."""
        return await User.filter(email=email).exclude(id=except_user_id).exists()

    async def taken_identifiers(self, *, username: str, email: str) -> frozenset[str]:
        """Which of `username` and `email` other accounts already use."""
        users = await User.filter(Q(username=username) | Q(email=email)).only(
            "id", "username", "email"
        )
        return frozenset(
            field
            for user in users
            for field, value in (("username", username), ("email", email))
            if getattr(user, field) == value
        )

    async def get_user(self, user_id: UUID) -> UserRecord | None:
        user = await User.get_or_none(id=user_id).select_related("role")
        return None if user is None else _record(user)

    async def list_users(self, *, limit: int, offset: int) -> list[UserRecord]:
        """One page of accounts, oldest first; the ID breaks ties, so pages are stable."""
        users = (
            await User.all()
            .select_related("role")
            .order_by("created_at", "id")
            .offset(offset)
            .limit(limit)
        )
        return [_record(user) for user in users]

    async def count_users(self) -> int:
        return await User.all().count()

    async def update_user(
        self, user_id: UUID, changes: UserChanges, *, keep_active_holder_of: str | None = None
    ) -> bool:
        """Apply `changes`; `None` fields stay unchanged.

        With `keep_active_holder_of`, the change is applied only if afterwards at least
        one active account still holds that permission; otherwise nothing changes and
        the result is False. A transaction-scoped advisory lock serialises these
        guarded changes, so two administrators demoting each other at the same
        moment cannot both succeed.
        """
        values: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if changes.full_name is not None:
            values["full_name"] = changes.full_name
        if changes.email is not None:
            values["email"] = changes.email
        if changes.is_active is not None:
            values["is_active"] = changes.is_active
        try:
            async with in_transaction() as connection:
                if changes.role_name is not None:
                    role = await Role.get(name=changes.role_name, using_db=connection)
                    values["role_id"] = role.id
                if keep_active_holder_of is not None:
                    await connection.execute_query(
                        "SELECT pg_advisory_xact_lock($1)", [ACCOUNT_GUARD_LOCK_ID]
                    )
                await User.filter(id=user_id).using_db(connection).update(**values)
                if keep_active_holder_of is not None and not await _has_active_holder(
                    connection, keep_active_holder_of
                ):
                    raise _GuardFailedError
        except _GuardFailedError:
            return False
        except IntegrityError as exc:
            # The service checks first; this covers a concurrent request taking the
            # email in between. Email is the only unique column changed here.
            raise ConflictError(EMAIL_TAKEN_MESSAGE, code=ErrorCode.EMAIL_TAKEN) from exc
        return True

    async def replace_password(self, user_id: UUID, password_hash: str) -> None:
        """Store a new password hash and revoke every token, in one statement."""
        await User.filter(id=user_id).update(
            password_hash=password_hash,
            token_version=F("token_version") + 1,
            updated_at=datetime.now(UTC),
        )

    async def increment_token_version(self, user_id: UUID) -> None:
        """Invalidate every token issued so far, atomically in the database."""
        # A bulk update skips auto_now, so updated_at is set explicitly.
        await User.filter(id=user_id).update(
            token_version=F("token_version") + 1, updated_at=datetime.now(UTC)
        )


class _GuardFailedError(Exception):
    """Leaves a transaction block so that it rolls back."""


def _record(user: User) -> UserRecord:
    role: Role = user.role
    return UserRecord(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=role.name,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def _has_active_holder(connection: BaseDBAsyncClient, permission: str) -> bool:
    return (
        await User.filter(is_active=True, role__permissions__code=permission)
        .using_db(connection)
        .exists()
    )
