"""Access tokens: content, time window with leeway, and every kind of tampering.

Role: pins backend.core.tokens `JwtTokenService`: tokens round-trip, carry identity but no
  permissions, each has its own id; expiry and not-before honour the leeway; a wrong
  signature, issuer, audience or algorithm, an unsigned token, missing or malformed claims and
  garbage are all INVALID_TOKEN; `user_id_or_none` reads a valid token only; and
  backend.core.settings rejects a signing key shorter than 32 bytes.
Used by: pytest (unit).
Depends on: PyJWT to forge and inspect tokens; an injected clock; the autouse
  `_required_environment` from tests/unit/backend/conftest.py. No services.
Key invariants: time is moved by the injected clock, never by waiting; forged tokens use the
  real secret, so only the check under test can reject them.
"""

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from pydantic import SecretStr, ValidationError

from backend.core.settings import BackendSettings
from backend.core.tokens import JwtTokenService
from common_lib.errors import AuthenticationError, ErrorCode

SECRET = "test-only-not-a-secret-signing-key-32-bytes-long"
USER_ID = UUID("00000000-0000-4000-8000-0000000000aa")
LEEWAY = timedelta(seconds=10)
LIFETIME = timedelta(minutes=30)


def service(
    *, now: datetime | None = None, secret: str = SECRET, issuer: str = "ethera-eval"
) -> JwtTokenService:
    return JwtTokenService(
        secret=SecretStr(secret),
        issuer=issuer,
        audience="ethera-eval",
        lifetime=LIFETIME,
        leeway=LEEWAY,
        clock=(lambda: now) if now else (lambda: datetime.now(UTC)),
    )


def assert_rejected(token: str) -> None:
    with pytest.raises(AuthenticationError) as rejected:
        service().decode(token)
    assert rejected.value.code is ErrorCode.INVALID_TOKEN


def forge(payload: dict[str, object], header: dict[str, object]) -> str:
    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part(header)}.{part(payload)}."


def test_issued_token_round_trips() -> None:
    issued = service().issue(USER_ID, token_version=3)

    claims = service().decode(issued.token)

    assert claims.user_id == USER_ID
    assert claims.token_version == 3
    assert issued.expires_in == 30 * 60


def test_token_holds_identity_but_no_permissions() -> None:
    payload = jwt.decode(service().issue(USER_ID, 0).token, options={"verify_signature": False})

    assert set(payload) == {"sub", "ver", "jti", "iss", "aud", "iat", "nbf", "exp"}


def test_every_token_has_its_own_id() -> None:
    first = service().decode(service().issue(USER_ID, 0).token)
    second = service().decode(service().issue(USER_ID, 0).token)

    assert first.token_id != second.token_id


def test_expired_token_is_rejected() -> None:
    issued_long_ago = datetime.now(UTC) - LIFETIME - LEEWAY - timedelta(seconds=5)

    assert_rejected(service(now=issued_long_ago).issue(USER_ID, 0).token)


def test_token_expired_within_the_leeway_is_accepted() -> None:
    issued = datetime.now(UTC) - LIFETIME - timedelta(seconds=5)

    assert service().decode(service(now=issued).issue(USER_ID, 0).token).user_id == USER_ID


def test_token_from_the_future_is_rejected_beyond_the_leeway() -> None:
    future = datetime.now(UTC) + LEEWAY + timedelta(seconds=30)

    assert_rejected(service(now=future).issue(USER_ID, 0).token)


def test_wrong_signature_is_rejected() -> None:
    assert_rejected(
        service(secret="another-secret-that-is-also-32-bytes!!").issue(USER_ID, 0).token
    )


def test_wrong_issuer_is_rejected() -> None:
    assert_rejected(service(issuer="someone-else").issue(USER_ID, 0).token)


def test_wrong_audience_is_rejected() -> None:
    other = JwtTokenService(
        secret=SecretStr(SECRET),
        issuer="ethera-eval",
        audience="another_api",
        lifetime=LIFETIME,
        leeway=LEEWAY,
    )

    assert_rejected(other.issue(USER_ID, 0).token)


def test_unsigned_token_is_rejected() -> None:
    payload = jwt.decode(service().issue(USER_ID, 0).token, options={"verify_signature": False})

    assert_rejected(forge(payload, {"alg": "none", "typ": "JWT"}))


# The forged HS512 token uses our 48-byte HS256 key, which PyJWT rightly calls short for HS512.
@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
def test_other_algorithm_with_the_same_secret_is_rejected() -> None:
    payload = jwt.decode(service().issue(USER_ID, 0).token, options={"verify_signature": False})

    assert_rejected(jwt.encode(payload, SECRET, algorithm="HS512"))


@pytest.mark.parametrize("claim", ["ver", "jti", "sub", "exp", "nbf", "iat"])
def test_missing_claim_is_rejected(claim: str) -> None:
    payload = jwt.decode(service().issue(USER_ID, 0).token, options={"verify_signature": False})
    del payload[claim]

    assert_rejected(jwt.encode(payload, SECRET, algorithm="HS256"))


@pytest.mark.parametrize(("claim", "value"), [("sub", "not-a-uuid"), ("ver", "1"), ("ver", True)])
def test_malformed_claim_is_rejected(claim: str, value: object) -> None:
    payload = jwt.decode(service().issue(USER_ID, 0).token, options={"verify_signature": False})
    payload[claim] = value

    assert_rejected(jwt.encode(payload, SECRET, algorithm="HS256"))


@pytest.mark.parametrize("token", ["", "not-a-token", "a.b.c", str(uuid4())])
def test_garbage_is_rejected(token: str) -> None:
    assert_rejected(token)


def test_short_signing_key_stops_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "x" * 31)

    with pytest.raises(ValidationError, match="at least 32 bytes"):
        BackendSettings()


def test_user_id_of_a_valid_token_is_known_without_loading_the_user() -> None:
    token = service().issue(USER_ID, token_version=3).token

    assert service().user_id_or_none(token) == USER_ID


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        service(secret="test-only-another-signing-key-32-bytes-x").issue(USER_ID, 0).token,
        service(now=datetime.now(UTC) - timedelta(hours=2)).issue(USER_ID, 0).token,
    ],
    ids=["garbage", "wrong signature", "expired"],
)
def test_user_id_of_an_invalid_token_is_none(token: str) -> None:
    assert service().user_id_or_none(token) is None
