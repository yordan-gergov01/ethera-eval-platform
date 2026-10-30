"""UserService with fakes: rules, stored changes and what is logged.

Role: pins backend.services.users `UserService`: self-service profile and password changes,
  admin create, read, list and update, the self-modification ban, the last-admin guard
  requested for demotions and deactivations, and the events it logs.
Used by: pytest (unit).
Depends on: local fakes `FakeUsers` (the user repository) and `FakeHasher`; a `log_lines`
  fixture over common_lib.logging_config `configure_logging`; the schemas in
  common_lib.schemas.users. No services.
Key invariants: a rejected change stores nothing; passwords and new email addresses never
  reach the logs; the guard itself is the repository's (covered by
  tests/integration/test_users_admin.py), here only whether the service asks for it.
"""

import io
import json
import logging
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
import structlog
from pydantic import SecretStr

from backend.core.security import PasswordCheck
from backend.dal.users import NewUser, UserChanges, UserRecord
from backend.services.auth import CurrentUser
from backend.services.users import UserService
from common_lib.errors import (
    BusinessRuleError,
    ConflictError,
    ErrorCode,
    NotFoundError,
    PermissionDeniedError,
)
from common_lib.logging_config import configure_logging
from common_lib.permissions import Permission, RoleName
from common_lib.schemas.password import WeakPasswordError
from common_lib.schemas.users import PasswordChange, UserAdminUpdate, UserCreate, UserSelfUpdate

CURRENT_PASSWORD = "test-only-current-password"
NEW_PASSWORD = "test-only-brand-new-password"
ALICE_ID = UUID("00000000-0000-4000-8000-0000000000aa")
BOB_ID = UUID("00000000-0000-4000-8000-0000000000bb")
NEW_ID = UUID("00000000-0000-4000-8000-0000000000cc")
ALICE = CurrentUser(
    id=ALICE_ID,
    username="alice",
    email="alice@example.com",
    full_name="Alice",
    role="admin",
    permissions=frozenset(Permission),
)
NOW = datetime(2026, 10, 6, tzinfo=UTC)


def record(user_id: UUID, username: str, role: str = "user", *, active: bool = True) -> UserRecord:
    return UserRecord(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        full_name=username.title(),
        role=role,
        is_active=active,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeUsers:
    def __init__(
        self,
        *,
        taken_emails: frozenset[str] = frozenset(),
        taken: frozenset[str] = frozenset(),
        guard_holds: bool = True,
    ) -> None:
        self.records = {
            ALICE_ID: record(ALICE_ID, "alice", "admin"),
            BOB_ID: record(BOB_ID, "bob", "admin"),
        }
        self.taken_emails = taken_emails
        self.taken = taken
        self.guard_holds = guard_holds
        self.updates: list[tuple[UUID, UserChanges, str | None]] = []
        self.created: list[NewUser] = []
        self.new_hashes: list[str] = []

    async def get_password_hash(self, user_id: UUID) -> str | None:
        return "stored-hash"

    async def email_in_use(self, email: str, *, except_user_id: UUID) -> bool:
        return email in self.taken_emails

    async def taken_identifiers(self, *, username: str, email: str) -> frozenset[str]:
        return self.taken

    async def get_user(self, user_id: UUID) -> UserRecord | None:
        return self.records.get(user_id)

    async def list_users(self, *, limit: int, offset: int) -> list[UserRecord]:
        return list(self.records.values())[offset : offset + limit]

    async def count_users(self) -> int:
        return len(self.records)

    async def create(self, user: NewUser) -> UUID:
        self.created.append(user)
        self.records[NEW_ID] = record(NEW_ID, user.username, user.role_name)
        return NEW_ID

    async def update_user(
        self, user_id: UUID, changes: UserChanges, *, keep_active_holder_of: str | None = None
    ) -> bool:
        self.updates.append((user_id, changes, keep_active_holder_of))
        if keep_active_holder_of is not None and not self.guard_holds:
            return False
        current = self.records[user_id]
        self.records[user_id] = replace(
            current,
            role=changes.role_name or current.role,
            is_active=current.is_active if changes.is_active is None else changes.is_active,
        )
        return True

    async def replace_password(self, user_id: UUID, password_hash: str) -> None:
        self.new_hashes.append(password_hash)


class FakeHasher:
    async def hash(self, password: str) -> str:
        return f"hash-of-{password}"

    async def verify(self, password: str, password_hash: str) -> PasswordCheck:
        return PasswordCheck(valid=password == CURRENT_PASSWORD)

    async def verify_dummy(self, password: str) -> None:
        pass


@pytest.fixture
def log_lines() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    configure_logging(service="test", stream=stream)
    yield stream
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


def events(stream: io.StringIO, name: str) -> list[dict[str, object]]:
    return [e for e in map(json.loads, stream.getvalue().splitlines()) if e["event"] == name]


def service(users: FakeUsers) -> UserService:
    return UserService(users, FakeHasher())


def password_change(current: str, new: str) -> PasswordChange:
    return PasswordChange(current_password=SecretStr(current), new_password=SecretStr(new))


def new_user(password: str = NEW_PASSWORD) -> UserCreate:
    return UserCreate(
        username="carol",
        email="carol@example.com",
        full_name="Carol",
        password=SecretStr(password),
        role=RoleName.USER,
    )


# --- Self-service ----------------------------------------------------------------------


async def test_profile_update_stores_only_the_given_fields(log_lines: io.StringIO) -> None:
    users = FakeUsers()

    updated = await service(users).update_own_profile(
        ALICE, UserSelfUpdate(email="alice@new.example.com")
    )

    assert users.updates == [(ALICE_ID, UserChanges(email="alice@new.example.com"), None)]
    assert updated == ALICE.model_copy(update={"email": "alice@new.example.com"})
    [logged] = events(log_lines, "user_updated")
    assert logged["fields"] == ["email"]
    assert "alice@new.example.com" not in log_lines.getvalue()


async def test_taken_email_changes_nothing() -> None:
    users = FakeUsers(taken_emails=frozenset({"bob@example.com"}))

    with pytest.raises(ConflictError) as raised:
        await service(users).update_own_profile(ALICE, UserSelfUpdate(email="bob@example.com"))

    assert raised.value.code is ErrorCode.EMAIL_TAKEN
    assert users.updates == []


async def test_password_change_stores_the_new_hash(log_lines: io.StringIO) -> None:
    users = FakeUsers()

    await service(users).change_own_password(ALICE, password_change(CURRENT_PASSWORD, NEW_PASSWORD))

    assert users.new_hashes == [f"hash-of-{NEW_PASSWORD}"]
    assert len(events(log_lines, "password_changed")) == 1
    assert CURRENT_PASSWORD not in log_lines.getvalue()
    assert NEW_PASSWORD not in log_lines.getvalue()


async def test_wrong_current_password_changes_nothing(log_lines: io.StringIO) -> None:
    users = FakeUsers()

    with pytest.raises(BusinessRuleError) as raised:
        await service(users).change_own_password(
            ALICE, password_change("a-wrong-guess-here", NEW_PASSWORD)
        )

    assert raised.value.code is ErrorCode.INVALID_CURRENT_PASSWORD
    assert users.new_hashes == []
    [failure] = events(log_lines, "password_change_failed")
    assert failure["reason"] == "wrong_current_password"


async def test_weak_new_password_changes_nothing() -> None:
    users = FakeUsers()

    with pytest.raises(BusinessRuleError) as raised:
        await service(users).change_own_password(
            ALICE, password_change(CURRENT_PASSWORD, "Alice@Example.com")
        )

    assert raised.value.code is ErrorCode.WEAK_PASSWORD
    assert isinstance(raised.value.__cause__, WeakPasswordError)
    assert users.new_hashes == []


# --- Administration --------------------------------------------------------------------


async def test_create_hashes_the_password_and_assigns_the_role(log_lines: io.StringIO) -> None:
    users = FakeUsers()

    created = await service(users).create_user(new_user())

    [stored] = users.created
    assert stored.password_hash == f"hash-of-{NEW_PASSWORD}"
    assert stored.role_name == "user"
    assert created.id == NEW_ID
    [logged] = events(log_lines, "user_created")
    assert logged["role"] == "user"
    assert NEW_PASSWORD not in log_lines.getvalue()


@pytest.mark.parametrize(
    ("taken", "code"),
    [
        (frozenset({"username"}), ErrorCode.USERNAME_TAKEN),
        (frozenset({"email"}), ErrorCode.EMAIL_TAKEN),
        (frozenset({"username", "email"}), ErrorCode.USERNAME_TAKEN),
    ],
)
async def test_create_with_a_taken_identifier_is_a_conflict(
    taken: frozenset[str], code: ErrorCode
) -> None:
    users = FakeUsers(taken=taken)

    with pytest.raises(ConflictError) as raised:
        await service(users).create_user(new_user())

    assert raised.value.code is code
    assert users.created == []


async def test_create_with_a_weak_password_is_rejected() -> None:
    users = FakeUsers()

    with pytest.raises(BusinessRuleError) as raised:
        await service(users).create_user(new_user(password="carol@example.com"))

    assert raised.value.code is ErrorCode.WEAK_PASSWORD
    assert users.created == []


async def test_unknown_user_is_404() -> None:
    with pytest.raises(NotFoundError) as raised:
        await service(FakeUsers()).get_user(NEW_ID)

    assert raised.value.code is ErrorCode.USER_NOT_FOUND


async def test_list_returns_the_page_and_the_total() -> None:
    page = await service(FakeUsers()).list_users(limit=1, offset=1)

    assert [user.username for user in page.items] == ["bob"]
    assert (page.total, page.limit, page.offset) == (2, 1, 1)


@pytest.mark.parametrize(
    "changes",
    [
        UserAdminUpdate(role=RoleName.USER),
        UserAdminUpdate(is_active=False),
        UserAdminUpdate(full_name="Alice A.", role=RoleName.USER),
    ],
)
async def test_nobody_changes_their_own_role_or_status(
    changes: UserAdminUpdate, log_lines: io.StringIO
) -> None:
    users = FakeUsers()

    with pytest.raises(PermissionDeniedError) as raised:
        await service(users).update_user(ALICE, ALICE_ID, changes)

    assert raised.value.code is ErrorCode.SELF_MODIFICATION_FORBIDDEN
    assert users.updates == []
    assert len(events(log_lines, "self_modification_denied")) == 1


async def test_own_name_and_unchanged_role_are_allowed() -> None:
    users = FakeUsers()

    await service(users).update_user(
        ALICE,
        ALICE_ID,
        UserAdminUpdate(full_name="Alice A.", role=RoleName.ADMIN, is_active=True),
    )

    [(_, _, guard)] = users.updates
    assert guard is None


@pytest.mark.parametrize(
    "changes",
    [UserAdminUpdate(role=RoleName.USER), UserAdminUpdate(is_active=False)],
)
async def test_demotion_and_deactivation_are_guarded(changes: UserAdminUpdate) -> None:
    users = FakeUsers()

    await service(users).update_user(ALICE, BOB_ID, changes)

    [(_, _, guard)] = users.updates
    assert guard == "users:update"


async def test_name_change_is_not_guarded() -> None:
    users = FakeUsers()

    await service(users).update_user(ALICE, BOB_ID, UserAdminUpdate(full_name="Robert"))

    [(_, _, guard)] = users.updates
    assert guard is None


async def test_failed_guard_is_last_admin_protected(log_lines: io.StringIO) -> None:
    users = FakeUsers(guard_holds=False)

    with pytest.raises(ConflictError) as raised:
        await service(users).update_user(ALICE, BOB_ID, UserAdminUpdate(is_active=False))

    assert raised.value.code is ErrorCode.LAST_ADMIN_PROTECTED
    assert users.records[BOB_ID].is_active
    assert len(events(log_lines, "last_admin_protected")) == 1


async def test_deactivation_is_logged(log_lines: io.StringIO) -> None:
    updated = await service(FakeUsers()).update_user(
        ALICE, BOB_ID, UserAdminUpdate(is_active=False)
    )

    assert not updated.is_active
    [logged] = events(log_lines, "user_deactivated")
    assert logged["target_user_id"] == str(BOB_ID)


async def test_update_of_an_unknown_user_is_404() -> None:
    users = FakeUsers()

    with pytest.raises(NotFoundError) as raised:
        await service(users).update_user(ALICE, NEW_ID, UserAdminUpdate(full_name="X"))

    assert raised.value.code is ErrorCode.USER_NOT_FOUND
    assert users.updates == []
