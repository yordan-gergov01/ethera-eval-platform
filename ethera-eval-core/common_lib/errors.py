"""Application errors, grouped by meaning rather than by transport.

Role: `ErrorCode` (every code a client can receive) and the `AppError` hierarchy that services
  raise.
Used by: the API (`backend.api.errors`, middleware, dependencies), services (auth, rate_limit,
  users), `backend.core.tokens`, `backend.core.long_poll`, `backend.dal.users.repository`,
  `backend.messaging.publisher`, and their tests.
Depends on: the standard library only.
Key invariants: only the HTTP layer knows which status code each error maps to (template_core
  D-005). Every error carries a stable machine-readable `code` and a message safe to show a
  client; `ErrorCode` values are part of the API and are never renamed. Infrastructure failures
  are wrapped and chained (`raise ... from exc`) so the original traceback stays in the logs.
  ORM-free (import-linter).
"""

from enum import StrEnum
from typing import ClassVar


class ErrorCode(StrEnum):
    """Every error code a client can receive. Values are part of the API: never rename one.

    A new, more specific code is added here and passed at the raise site, for
    example `NotFoundError(code=ErrorCode.USER_NOT_FOUND)`.
    """

    # Raised by services.
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_TOKEN = "INVALID_TOKEN"  # noqa: S105 - an error code name, not a secret
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    BROKER_UNAVAILABLE = "BROKER_UNAVAILABLE"
    TOO_MANY_CONCURRENT_POLLS = "TOO_MANY_CONCURRENT_POLLS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USERNAME_TAKEN = "USERNAME_TAKEN"
    EMAIL_TAKEN = "EMAIL_TAKEN"
    SELF_MODIFICATION_FORBIDDEN = "SELF_MODIFICATION_FORBIDDEN"
    LAST_ADMIN_PROTECTED = "LAST_ADMIN_PROTECTED"
    WEAK_PASSWORD = "WEAK_PASSWORD"  # noqa: S105 - an error code name, not a secret
    INVALID_CURRENT_PASSWORD = "INVALID_CURRENT_PASSWORD"  # noqa: S105 - an error code name

    # Produced by the HTTP layer itself.
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """Base of all expected application errors."""

    default_code: ClassVar[ErrorCode] = ErrorCode.INTERNAL_ERROR
    default_message: ClassVar[str] = "The request could not be completed."

    def __init__(self, message: str | None = None, *, code: ErrorCode | None = None) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class AuthenticationError(AppError):
    """Missing, invalid, expired or revoked credentials."""

    default_code = ErrorCode.AUTHENTICATION_FAILED
    default_message = "Authentication is required or the credentials are not valid."


class PermissionDeniedError(AppError):
    """The caller is authenticated but lacks a required permission."""

    default_code = ErrorCode.PERMISSION_DENIED
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    """The resource does not exist, or the caller may not know that it exists."""

    default_code = ErrorCode.NOT_FOUND
    default_message = "The requested resource does not exist."


class ConflictError(AppError):
    """The request conflicts with existing data, such as a duplicate username."""

    default_code = ErrorCode.CONFLICT
    default_message = "The request conflicts with the current state of the resource."


class BusinessRuleError(AppError):
    """The request is well-formed but breaks a business rule."""

    default_code = ErrorCode.BUSINESS_RULE_VIOLATION
    default_message = "The request breaks a business rule."


class RateLimitExceededError(AppError):
    """Too many requests in the current window."""

    default_code = ErrorCode.RATE_LIMITED
    default_message = "Too many requests. Try again later."

    def __init__(
        self,
        retry_after_seconds: int,
        message: str | None = None,
        *,
        limit: int | None = None,
        code: ErrorCode | None = None,
    ) -> None:
        super().__init__(message, code=code)
        self.retry_after_seconds = retry_after_seconds
        # The request rate limit that was exceeded, for the X-RateLimit-* headers; None
        # for other limits, such as the cap on concurrent long polls.
        self.limit = limit


class ServiceUnavailableError(AppError):
    """A dependency such as the database or the message broker is unavailable."""

    default_code = ErrorCode.SERVICE_UNAVAILABLE
    default_message = "The service is temporarily unavailable. Try again later."
