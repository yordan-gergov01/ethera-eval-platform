"""Signed, short-lived access tokens (JWT, HS256).

Role: `JwtTokenService` issues and validates access tokens; `user_id_or_none` tells callers apart
  for rate limiting.
Used by: `backend.main` (one service per process on `app.state`), `backend.services.auth.service`,
  and `backend.api.dependencies.rate_limit` (through `app.state.token_service`).
Depends on: PyJWT, `common_lib.errors` (`AuthenticationError`, `ErrorCode.INVALID_TOKEN`).
Key invariants: a token carries the user ID and token version, nothing else — no role and no
  permissions, which are loaded from the database on every request; logout or a password
  change increases the version and rejects every earlier token (template_core D-006; kept for the
  PoC by D-013). Only HS256 is accepted and all of `REQUIRED_CLAIMS` must be present. Every
  failure is the same 401 for the client; the reason is logged. `user_id_or_none` never raises
  or logs and is not authentication. Covered by the 100% auth coverage gate (D-008).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import structlog
from pydantic import SecretStr

from common_lib.errors import AuthenticationError, ErrorCode

ALGORITHM = "HS256"
REQUIRED_CLAIMS = ("sub", "exp", "iat", "nbf", "jti", "iss", "aud", "ver")

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AccessToken:
    token: str
    expires_in: int  # seconds


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: UUID
    token_version: int
    token_id: str


class JwtTokenService:
    """Issues and validates access tokens."""

    def __init__(
        self,
        *,
        secret: SecretStr,
        issuer: str,
        audience: str,
        lifetime: timedelta,
        leeway: timedelta,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._lifetime = lifetime
        self._leeway = leeway
        self._clock = clock

    def issue(self, user_id: UUID, token_version: int) -> AccessToken:
        """Sign a token for the user at its current token version."""
        now = self._clock()
        claims = {
            "sub": str(user_id),
            "ver": token_version,
            "jti": uuid4().hex,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "nbf": now,
            "exp": now + self._lifetime,
        }
        token = jwt.encode(claims, self._secret.get_secret_value(), algorithm=ALGORITHM)
        return AccessToken(token=token, expires_in=int(self._lifetime.total_seconds()))

    def decode(self, token: str) -> TokenClaims:
        """Validate signature, algorithm, issuer, audience and time window; return the claims.

        Every failure is the same 401 for the client; the reason is logged.
        """
        try:
            return self._claims(token)
        except (jwt.InvalidTokenError, ValueError) as exc:
            logger.info("token_rejected", reason=type(exc).__name__)
            raise AuthenticationError(
                "The access token is invalid or has expired.", code=ErrorCode.INVALID_TOKEN
            ) from exc

    def user_id_or_none(self, token: str) -> UUID | None:
        """The user a valid token was issued to, or None; never raises or logs.

        For telling callers apart (rate limiting), not for authentication: the user
        is not loaded, so a revoked token or a deactivated user still yields an ID.
        """
        try:
            return self._claims(token).user_id
        except (jwt.InvalidTokenError, ValueError):
            # An invalid token is an expected answer here; authentication reports it.
            return None

    def _claims(self, token: str) -> TokenClaims:
        payload = jwt.decode(
            token,
            self._secret.get_secret_value(),
            algorithms=[ALGORITHM],
            audience=self._audience,
            issuer=self._issuer,
            leeway=self._leeway,
            options={"require": list(REQUIRED_CLAIMS)},
        )
        version = payload["ver"]
        if not isinstance(version, int) or isinstance(version, bool):
            raise jwt.InvalidTokenError("ver must be an integer")
        return TokenClaims(
            user_id=UUID(payload["sub"]), token_version=version, token_id=payload["jti"]
        )
