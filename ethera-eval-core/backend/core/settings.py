"""Typed settings of the backend, read once from environment variables at startup.

Role: `DatabaseSettings` (PostgreSQL connection: the runtime role that serves requests and the
  migration owner that migrates and seeds) and `BackendSettings` (everything the backend
  service needs: JWT, admin account, API docs, CORS, body limit, trusted proxies, rate limits,
  plus the broker settings).
Used by: `backend.main`, `backend.core.database`, `backend.core.startup`,
  `backend.core.job_waiter`, and the `backend` barrel (`evals.app`, `evals.migration_cli`).
Depends on: `common_lib.settings` (`ServiceSettings`, `BrokerSettings`),
  `common_lib.schemas.identity` and `common_lib.schemas.password` (admin account validation).
Key invariants: `DatabaseSettings` stands alone for the migration command line. `db_user` is
  always the runtime role (NOBYPASSRLS, data grants only); the migration owner's pair is
  separate, must name another role, and is reached only through `for_owner()` (D-021, D-022
  Fork R2 = A). The JWT secret
  must be at least 32 bytes (RFC 7518 for HS256). The admin password must pass the password
  policy; the admin account is created on first start only and never updated from these values.
  CORS origins are explicit (no wildcard, path or trailing slash) and trusted proxies are IP
  addresses or networks, never a wildcard. Replicas x pool size must stay below PostgreSQL's
  max_connections. `.env.example` and compose must stay in step (tests/unit/test_env_example.py).
"""

import ipaddress
import re
from typing import Annotated, Self

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import NoDecode

from common_lib.schemas.identity import Email, Username
from common_lib.schemas.password import validate_password
from common_lib.settings import BrokerSettings, ServiceSettings

# scheme://host[:port], nothing else: browsers send exactly this as the Origin header.
_ORIGIN_RE = re.compile(r"^https?://[A-Za-z0-9.-]+(:\d{1,5})?$")
# HS256 needs a key at least as long as its 256-bit output (RFC 7518, section 3.2).
MIN_JWT_SECRET_BYTES = 32


class DatabaseSettings(ServiceSettings):
    """Connection to PostgreSQL. Also used on its own by the migration command line.

    `db_user` is the runtime role every request uses; `db_owner_user` is the migration owner
    used only at startup, under the startup lock (D-021).
    """

    db_host: str = "postgres"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str
    db_user: str
    db_password: SecretStr
    # The migration owner: owns the schema, runs migrations and seeds, holds BYPASSRLS.
    db_owner_user: str
    db_owner_password: SecretStr
    # Upper bound of each replica's connection pool. Replicas x pool size must stay
    # below PostgreSQL's max_connections (100 by default).
    db_pool_max_size: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def _owner_is_another_role(self) -> Self:
        # One role for both would put BYPASSRLS on every request (D-014).
        if self.db_owner_user == self.db_user:
            raise ValueError("db_owner_user must name another role than db_user")
        return self

    def for_owner(self) -> Self:
        """The same settings with the migration owner's credentials as the connecting role."""
        return self.model_copy(
            update={"db_user": self.db_owner_user, "db_password": self.db_owner_password}
        )


class BackendSettings(DatabaseSettings, BrokerSettings):
    """All settings of the backend service."""

    # HS256 signing key for access tokens; at least 32 bytes (256 bits).
    jwt_secret: SecretStr
    jwt_issuer: str = "ethera-eval"
    jwt_audience: str = "ethera-eval"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    # Tolerated clock difference between servers when checking exp and nbf.
    jwt_leeway_seconds: int = Field(default=10, ge=0, le=300)

    # The admin account created on first start if no user with this name exists. It is
    # never updated afterwards, so changing these values later has no effect.
    admin_username: Username
    admin_email: Email
    admin_password: SecretStr

    # Interactive OpenAPI page at /docs; switch off where the API shape should not be public.
    enable_api_docs: bool = True
    # Comma-separated list of frontend origins allowed to call the API from a browser.
    cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:3000",)
    # Larger request bodies are rejected with 413 before they are parsed.
    max_request_body_bytes: int = Field(default=1_048_576, ge=1024)
    # Comma-separated addresses or networks (CIDR) of reverse proxies whose
    # X-Forwarded-For header is trusted for the client address. Empty: trust nobody.
    trusted_proxies: Annotated[tuple[str, ...], NoDecode] = ()

    # Requests per window for every /api/v1 request, keyed by user (valid token) or IP.
    rate_limit_default_requests: int = Field(default=120, ge=1)
    rate_limit_default_window_seconds: int = Field(default=60, ge=1, le=86_400)
    # Login attempts per window, keyed by client IP and username.
    rate_limit_login_requests: int = Field(default=5, ge=1)
    rate_limit_login_window_seconds: int = Field(default=60, ge=1, le=86_400)

    @field_validator("jwt_secret")
    @classmethod
    def _secret_is_long_enough(cls, secret: SecretStr) -> SecretStr:
        if len(secret.get_secret_value().encode()) < MIN_JWT_SECRET_BYTES:
            raise ValueError(f"must be at least {MIN_JWT_SECRET_BYTES} bytes long")
        return secret

    @field_validator("admin_password")
    @classmethod
    def _admin_password_meets_the_policy(
        cls, password: SecretStr, info: ValidationInfo
    ) -> SecretStr:
        # Username and email are declared first, so they are already validated here.
        validate_password(
            password.get_secret_value(),
            username=info.data.get("admin_username", ""),
            email=info.data.get("admin_email", ""),
        )
        return password

    @field_validator("cors_allowed_origins", "trusted_proxies", mode="before")
    @classmethod
    def _split_list(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def _origins_are_explicit(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        if not origins:
            raise ValueError("at least one origin is required")
        for origin in origins:
            if not _ORIGIN_RE.fullmatch(origin):
                raise ValueError(
                    f"{origin!r} is not an explicit origin like http://localhost:3000 "
                    "(no wildcard, path or trailing slash)"
                )
        return origins

    @field_validator("trusted_proxies")
    @classmethod
    def _proxies_are_addresses(cls, proxies: tuple[str, ...]) -> tuple[str, ...]:
        for proxy in proxies:
            try:
                ipaddress.ip_network(proxy, strict=False)
            except ValueError as exc:
                # No wildcard: trusting every sender would let any client choose its address.
                raise ValueError(
                    f"{proxy!r} is not an IP address or network like 172.18.0.0/16"
                ) from exc
        return proxies
