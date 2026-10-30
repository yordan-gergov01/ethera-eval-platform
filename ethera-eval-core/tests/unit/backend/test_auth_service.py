"""AuthService with fakes: one answer for every login failure, the reason in the logs.

Role: pins backend.services.auth `AuthService`: login with a normalised username and the
  current token version, one INVALID_CREDENTIALS answer for every failure with the real reason
  logged, a dummy verification for unknown users, hash upgrades only on success, token to
  current user with fresh permissions, logout revoking every token.
Used by: pytest (unit).
Depends on: local fakes `FakeUsers`, `FakeHasher`, `FakeTokens` in place of the user
  repository, the password hasher and the token service; the local `log_lines` fixture over
  common_lib.logging_config `configure_logging`. No services.
Key invariants: passwords never reach the logs; a failed login never stores a hash; an
  inactive, revoked or vanished account's token is INVALID_TOKEN with the reason logged.
"""

import io
import json
import logging
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
import structlog

from backend.core.security import PasswordCheck
from backend.core.tokens import AccessToken, TokenClaims
from backend.dal.users import Credentials, UserProfile
from backend.services.auth import AuthService, CurrentUser
from common_lib.errors import AuthenticationError, ErrorCode
from common_lib.logging_config import configure_logging
from common_lib.permissions import Permission

PASSWORD = "correct horse battery staple"
USER_ID = UUID("00000000-0000-4000-8000-0000000000aa")


class FakeUsers:
    def __init__(self, *, active: bool = True, token_version: int = 0) -> None:
        self.active = active
        self.token_version = token_version
        self.exists = True
        self.lookups: list[str] = []
        self.stored_hashes: list[str] = []

    async def get_credentials(self, username: str) -> Credentials | None:
        self.lookups.append(username)
        if not self.exists or username != "alice":
            return None
        return Credentials(
            user_id=USER_ID,
            password_hash="stored-hash",
            is_active=self.active,
            token_version=self.token_version,
        )

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        if not self.exists or user_id != USER_ID:
            return None
        return UserProfile(
            id=USER_ID,
            username="alice",
            email="alice@example.com",
            full_name="Alice",
            is_active=self.active,
            token_version=self.token_version,
            role="user",
            permissions=frozenset({"users:read", "users:update"}),
        )

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        self.stored_hashes.append(password_hash)

    async def increment_token_version(self, user_id: UUID) -> None:
        self.token_version += 1


class FakeHasher:
    def __init__(self, upgraded_hash: str | None = None) -> None:
        self.upgraded_hash = upgraded_hash
        self.dummy_verifications = 0

    async def hash(self, password: str) -> str:
        return "hash"

    async def verify(self, password: str, password_hash: str) -> PasswordCheck:
        valid = password == PASSWORD
        return PasswordCheck(valid=valid, upgraded_hash=self.upgraded_hash if valid else None)

    async def verify_dummy(self, password: str) -> None:
        self.dummy_verifications += 1


class FakeTokens:
    def issue(self, user_id: UUID, token_version: int) -> AccessToken:
        return AccessToken(token=f"{user_id}:{token_version}", expires_in=1800)

    def decode(self, token: str) -> TokenClaims:
        if token == "garbage":
            raise AuthenticationError(code=ErrorCode.INVALID_TOKEN)
        user_id, version = token.split(":")
        return TokenClaims(user_id=UUID(user_id), token_version=int(version), token_id="jti")


@pytest.fixture
def log_lines() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    configure_logging(service="test", stream=stream)
    yield stream
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


def events(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def service(users: FakeUsers, hasher: FakeHasher | None = None) -> AuthService:
    return AuthService(users=users, hasher=hasher or FakeHasher(), tokens=FakeTokens())


async def assert_invalid_credentials(auth: AuthService, username: str, password: str) -> None:
    with pytest.raises(AuthenticationError) as rejected:
        await auth.login(username, password)
    assert rejected.value.code is ErrorCode.INVALID_CREDENTIALS
    assert rejected.value.message == "The username or password is incorrect."


# --- Login -----------------------------------------------------------------------------


async def test_login_issues_a_token_for_the_current_token_version() -> None:
    token = await service(FakeUsers(token_version=4)).login("alice", PASSWORD)

    assert token.token == f"{USER_ID}:4"


@pytest.mark.parametrize("typed", ["Alice", " ALICE ", "ａｌｉｃｅ"])  # noqa: RUF001
async def test_username_is_normalised_before_the_lookup(typed: str) -> None:
    users = FakeUsers()

    await service(users).login(typed, PASSWORD)

    assert users.lookups == ["alice"]


async def test_wrong_password_is_rejected(log_lines: io.StringIO) -> None:
    await assert_invalid_credentials(service(FakeUsers()), "alice", "wrong password!")

    [failure] = [e for e in events(log_lines) if e["event"] == "login_failed"]
    assert failure["reason"] == "wrong_password"


async def test_unknown_user_costs_a_dummy_verification(log_lines: io.StringIO) -> None:
    hasher = FakeHasher()

    await assert_invalid_credentials(service(FakeUsers(), hasher), "mallory", PASSWORD)

    assert hasher.dummy_verifications == 1
    [failure] = [e for e in events(log_lines) if e["event"] == "login_failed"]
    assert failure["reason"] == "unknown_user"


async def test_inactive_user_gets_the_same_answer_and_the_reason_is_logged(
    log_lines: io.StringIO,
) -> None:
    await assert_invalid_credentials(service(FakeUsers(active=False)), "alice", PASSWORD)

    [failure] = [e for e in events(log_lines) if e["event"] == "login_failed"]
    assert failure["reason"] == "account_inactive"


async def test_passwords_never_reach_the_logs(log_lines: io.StringIO) -> None:
    await service(FakeUsers()).login("alice", PASSWORD)
    await assert_invalid_credentials(service(FakeUsers()), "alice", "another secret value")

    assert PASSWORD not in log_lines.getvalue()
    assert "another secret value" not in log_lines.getvalue()


async def test_outdated_hash_is_replaced_on_login() -> None:
    users = FakeUsers()

    await service(users, FakeHasher(upgraded_hash="fresh-hash")).login("alice", PASSWORD)

    assert users.stored_hashes == ["fresh-hash"]


async def test_failed_login_never_stores_a_hash() -> None:
    users = FakeUsers()

    await assert_invalid_credentials(
        service(users, FakeHasher(upgraded_hash="fresh-hash")), "alice", "wrong password!"
    )

    assert users.stored_hashes == []


# --- Token to current user -------------------------------------------------------------


async def test_valid_token_resolves_the_user_with_fresh_permissions() -> None:
    user = await service(FakeUsers()).authenticate(f"{USER_ID}:0")

    assert user == CurrentUser(
        id=USER_ID,
        username="alice",
        email="alice@example.com",
        full_name="Alice",
        role="user",
        permissions=frozenset({Permission.USERS_READ, Permission.USERS_UPDATE}),
    )


@pytest.mark.parametrize(
    ("setup", "token", "reason"),
    [
        ({"active": False}, f"{USER_ID}:0", "account_inactive"),
        ({"token_version": 1}, f"{USER_ID}:0", "token_revoked"),
        ({}, f"{uuid4()}:0", "user_not_found"),
    ],
)
async def test_token_of_an_unusable_account_is_rejected(
    log_lines: io.StringIO, setup: dict[str, object], token: str, reason: str
) -> None:
    with pytest.raises(AuthenticationError) as rejected:
        await service(FakeUsers(**setup)).authenticate(token)  # type: ignore[arg-type]

    assert rejected.value.code is ErrorCode.INVALID_TOKEN
    [rejection] = [e for e in events(log_lines) if e["event"] == "token_rejected"]
    assert rejection["reason"] == reason


async def test_logout_revokes_every_issued_token() -> None:
    users = FakeUsers()
    auth = service(users)
    token = (await auth.login("alice", PASSWORD)).token

    await auth.logout(await auth.authenticate(token))

    with pytest.raises(AuthenticationError):
        await auth.authenticate(token)
