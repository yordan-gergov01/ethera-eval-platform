"""Login, logout, and turning an access token into the current user.

Role: `AuthService` (login, authenticate, logout), the `CurrentUser` value, and
  `build_auth_service`, which wires it to the real repository.
Used by: `backend.services.auth` (re-export), and through it the API dependencies, routers and
  `backend.services.users.service`.
Depends on: `backend.core.tokens` (token types, `JwtTokenService`), `backend.dal.users`, the
  `PasswordHasher` Protocol, `common_lib.permissions`, `common_lib.schemas.identity`,
  `common_lib.errors`.
Key invariants: every login failure is the same 401 for the client and the real reason is
  logged; an unknown username still costs a full password verification, and the active flag is
  checked only after the password, so nothing reveals which accounts exist. The token only
  identifies the user: role and permissions are loaded fresh on every request, so a role change,
  a deactivation or a logout applies to the next request (template_core D-006). An outdated hash
  is upgraded on login. Covered by the 100% auth coverage gate (D-008).
"""

from typing import NoReturn, Protocol
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict

from backend.core.tokens import AccessToken, JwtTokenService, TokenClaims
from backend.dal.users import Credentials, UserProfile, UserRepository
from backend.services.protocols import PasswordHasher
from common_lib.errors import AuthenticationError, ErrorCode
from common_lib.permissions import Permission
from common_lib.schemas.identity import normalize_identifier

logger = structlog.get_logger(__name__)

INVALID_CREDENTIALS_MESSAGE = "The username or password is incorrect."


class UserStore(Protocol):
    async def get_credentials(self, username: str) -> Credentials | None: ...

    async def get_profile(self, user_id: UUID) -> UserProfile | None: ...

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None: ...

    async def increment_token_version(self, user_id: UUID) -> None: ...


class TokenIssuer(Protocol):
    def issue(self, user_id: UUID, token_version: int) -> AccessToken: ...

    def decode(self, token: str) -> TokenClaims: ...


class CurrentUser(BaseModel):
    """The authenticated caller, with the permissions it holds right now."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    username: str
    email: str
    full_name: str
    role: str
    permissions: frozenset[Permission]


class AuthService:
    def __init__(self, users: UserStore, hasher: PasswordHasher, tokens: TokenIssuer) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    async def login(self, username: str, password: str) -> AccessToken:
        """Check the credentials and issue an access token.

        Every failure is the same error for the client; the real reason is logged.
        An unknown username still costs a full password verification, so response
        times do not reveal which usernames exist.
        """
        username = normalize_identifier(username)
        credentials = await self._users.get_credentials(username)
        if credentials is None:
            await self._hasher.verify_dummy(password)
            self._reject_login(username, reason="unknown_user")

        check = await self._hasher.verify(password, credentials.password_hash)
        if not check.valid:
            self._reject_login(username, reason="wrong_password")
        if check.upgraded_hash is not None:
            await self._users.update_password_hash(credentials.user_id, check.upgraded_hash)
            logger.info("password_hash_upgraded", user_id=str(credentials.user_id))
        # Checked after the password, so a wrong password reveals nothing about the account.
        if not credentials.is_active:
            self._reject_login(username, reason="account_inactive")

        logger.info("login_succeeded", user_id=str(credentials.user_id))
        return self._tokens.issue(credentials.user_id, credentials.token_version)

    async def authenticate(self, token: str) -> CurrentUser:
        """Resolve a token to the current user, or raise 401.

        The token only identifies the user; the role and permissions are loaded
        fresh, so a change of role or a deactivation takes effect immediately.
        """
        claims = self._tokens.decode(token)
        profile = await self._users.get_profile(claims.user_id)
        if profile is None:
            self._reject_token(claims, reason="user_not_found")
        if not profile.is_active:
            self._reject_token(claims, reason="account_inactive")
        if profile.token_version != claims.token_version:
            self._reject_token(claims, reason="token_revoked")
        return CurrentUser(
            id=profile.id,
            username=profile.username,
            email=profile.email,
            full_name=profile.full_name,
            role=profile.role,
            permissions=frozenset(Permission(code) for code in profile.permissions),
        )

    async def logout(self, user: CurrentUser) -> None:
        """Revoke every token of the user, on every device."""
        await self._users.increment_token_version(user.id)
        logger.info("logout", user_id=str(user.id))

    @staticmethod
    def _reject_login(username: str, *, reason: str) -> NoReturn:
        logger.warning("login_failed", username=username, reason=reason)
        raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE, code=ErrorCode.INVALID_CREDENTIALS)

    @staticmethod
    def _reject_token(claims: TokenClaims, *, reason: str) -> NoReturn:
        logger.info("token_rejected", user_id=str(claims.user_id), reason=reason)
        raise AuthenticationError(
            "The access token is invalid or has expired.", code=ErrorCode.INVALID_TOKEN
        )


def build_auth_service(hasher: PasswordHasher, tokens: JwtTokenService) -> AuthService:
    """Wire the service to the real repository."""
    return AuthService(users=UserRepository(), hasher=hasher, tokens=tokens)
