"""Translation of every error into an RFC 9457 problem details response.

Role: the only place that knows how application errors map to HTTP. Every error response,
  including FastAPI's own (unknown route, wrong method, invalid body), has the same shape:
  `type`, `title`, `status`, `detail`, `instance`, `code`, `request_id`, and `errors` for
  field-level validation problems. Also builds the X-RateLimit-* headers and the OpenAPI
  description of error responses.
Used by: `backend.main` (handlers, header names), `backend.api.middleware`,
  `backend.api.v1.router` and the routers in `backend.api.v1` (`documented_problem`).
Depends on: `common_lib.errors` (the error classes and `ErrorCode`), FastAPI/Starlette, structlog.
Key invariants: services raise by meaning and know nothing about HTTP (template_core D-005).
  `_STATUS_BY_ERROR` lists subclasses before their bases. Validation errors never echo the
  rejected input (it may be a password). Database-unavailable driver errors are passed in by the
  factory, so this module never imports the database libraries; they become a 503 with
  Retry-After. X-RateLimit-Reset is in seconds, like Retry-After, not a timestamp.
"""

from collections.abc import Iterable, Mapping, Sequence
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from common_lib.errors import (
    AppError,
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    ErrorCode,
    NotFoundError,
    PermissionDeniedError,
    RateLimitExceededError,
    ServiceUnavailableError,
)

PROBLEM_MEDIA_TYPE = "application/problem+json"
# Suggested wait before retrying when a dependency (database, broker) is unavailable.
UNAVAILABLE_RETRY_AFTER_SECONDS = 5
INTERNAL_ERROR_DETAIL = (
    "An unexpected error occurred. Quote the request ID when reporting the problem."
)

logger = structlog.get_logger(__name__)

# Most specific first: a subclass must appear before its base.
_STATUS_BY_ERROR: Sequence[tuple[type[AppError], HTTPStatus]] = (
    (AuthenticationError, HTTPStatus.UNAUTHORIZED),
    (PermissionDeniedError, HTTPStatus.FORBIDDEN),
    (NotFoundError, HTTPStatus.NOT_FOUND),
    (ConflictError, HTTPStatus.CONFLICT),
    (BusinessRuleError, HTTPStatus.UNPROCESSABLE_ENTITY),
    (RateLimitExceededError, HTTPStatus.TOO_MANY_REQUESTS),
    (ServiceUnavailableError, HTTPStatus.SERVICE_UNAVAILABLE),
)

PAYLOAD_TOO_LARGE_DETAIL = "The request body is larger than the server accepts."

# Rate limit headers; X-RateLimit-Reset is in seconds, like Retry-After, not a timestamp.
RATE_LIMIT_LIMIT_HEADER = "X-RateLimit-Limit"
RATE_LIMIT_REMAINING_HEADER = "X-RateLimit-Remaining"
RATE_LIMIT_RESET_HEADER = "X-RateLimit-Reset"
RATE_LIMIT_HEADERS = (RATE_LIMIT_LIMIT_HEADER, RATE_LIMIT_REMAINING_HEADER, RATE_LIMIT_RESET_HEADER)

# Codes and client messages for HTTP errors raised by the framework itself.
_HTTP_ERRORS: Mapping[int, tuple[ErrorCode, str]] = {
    HTTPStatus.BAD_REQUEST: (ErrorCode.MALFORMED_REQUEST, "The request could not be read."),
    HTTPStatus.NOT_FOUND: (ErrorCode.NOT_FOUND, "The requested resource does not exist."),
    HTTPStatus.METHOD_NOT_ALLOWED: (
        ErrorCode.METHOD_NOT_ALLOWED,
        "This method is not allowed for the requested resource.",
    ),
    HTTPStatus.REQUEST_ENTITY_TOO_LARGE: (ErrorCode.PAYLOAD_TOO_LARGE, PAYLOAD_TOO_LARGE_DETAIL),
}


class FieldError(BaseModel):
    field: str
    message: str
    type: str


class ProblemDetails(BaseModel):
    """Body of every error response (RFC 9457)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: ErrorCode
    request_id: str | None = None
    errors: list[FieldError] | None = None


def documented_problem(description: str) -> dict[str, Any]:
    """OpenAPI description of an error response, for a route's `responses`."""
    return {
        "model": ProblemDetails,
        "description": description,
        "content": {PROBLEM_MEDIA_TYPE: {}},
    }


def problem_response(
    *,
    status: int,
    code: ErrorCode,
    detail: str,
    instance: str,
    request_id: str | None,
    errors: list[FieldError] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build a problem details response."""
    body = ProblemDetails(
        title=HTTPStatus(status).phrase,
        status=status,
        detail=detail,
        instance=instance,
        code=code,
        request_id=request_id,
        errors=errors,
    )
    return JSONResponse(
        body.model_dump(mode="json", exclude_none=True),
        status_code=status,
        headers=dict(headers or {}),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def internal_error_response(*, instance: str, request_id: str | None) -> JSONResponse:
    """The generic 500 response: no internals, only the request ID to quote."""
    return problem_response(
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        code=ErrorCode.INTERNAL_ERROR,
        detail=INTERNAL_ERROR_DETAIL,
        instance=instance,
        request_id=request_id,
    )


def register_exception_handlers(
    app: FastAPI, *, database_unavailable: Iterable[type[Exception]] = ()
) -> None:
    """Install the global handlers that turn every error into problem details.

    `database_unavailable` lists the driver exceptions that mean the database cannot
    be reached. They are handled here, once for the whole application, so no route,
    service or repository needs its own try/except for them. This module does not
    import the database libraries; the application factory passes the types in.
    """
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)  # type: ignore[arg-type]
    for error_type in database_unavailable:
        app.add_exception_handler(error_type, _handle_database_unavailable)


async def _handle_database_unavailable(request: Request, exc: Exception) -> JSONResponse:
    # A dependency is down, not a bug in the request: logged with the full traceback,
    # answered with 503 and a hint when to retry.
    logger.error("database_unavailable", exc_info=exc)
    return problem_response(
        status=HTTPStatus.SERVICE_UNAVAILABLE,
        code=ErrorCode.DATABASE_UNAVAILABLE,
        detail="The database is temporarily unavailable. Try again shortly.",
        instance=request.url.path,
        request_id=_request_id(request),
        headers={"Retry-After": str(UNAVAILABLE_RETRY_AFTER_SECONDS)},
    )


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    status = _status_for(exc)
    headers: dict[str, str] = {}
    if isinstance(exc, AuthenticationError):
        headers["WWW-Authenticate"] = "Bearer"
    if isinstance(exc, RateLimitExceededError):
        headers["Retry-After"] = str(exc.retry_after_seconds)
        if exc.limit is not None:
            headers |= rate_limit_headers(
                limit=exc.limit, remaining=0, reset_seconds=exc.retry_after_seconds
            )
    if isinstance(exc, ServiceUnavailableError):
        headers["Retry-After"] = str(UNAVAILABLE_RETRY_AFTER_SECONDS)

    if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        logger.error("request_failed", status=status, code=exc.code, exc_info=exc)
    else:
        _log_rejection(status, exc.code)

    return problem_response(
        status=status,
        code=exc.code,
        detail=exc.message,
        instance=request.url.path,
        request_id=_request_id(request),
        headers=headers,
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    raw_errors: Sequence[Mapping[str, Any]] = exc.errors()
    if any(error.get("type") == "json_invalid" for error in raw_errors):
        status, code = HTTPStatus.BAD_REQUEST, ErrorCode.MALFORMED_REQUEST
        detail, field_errors = "The request body is not valid JSON.", None
    else:
        status, code = HTTPStatus.UNPROCESSABLE_ENTITY, ErrorCode.VALIDATION_FAILED
        detail = "The request contains invalid values. See 'errors' for details."
        # Only location, message and type: the rejected input itself is never echoed,
        # because it may be a password.
        field_errors = [
            FieldError(
                field=".".join(str(part) for part in error.get("loc", ())),
                message=str(error.get("msg", "")),
                type=str(error.get("type", "")),
            )
            for error in raw_errors
        ]
    _log_rejection(status, code)
    return problem_response(
        status=status,
        code=code,
        detail=detail,
        instance=request.url.path,
        request_id=_request_id(request),
        errors=field_errors,
    )


async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, detail = _HTTP_ERRORS.get(
        exc.status_code, (ErrorCode.HTTP_ERROR, HTTPStatus(exc.status_code).description)
    )
    _log_rejection(exc.status_code, code)
    return problem_response(
        status=exc.status_code,
        code=code,
        detail=detail,
        instance=request.url.path,
        request_id=_request_id(request),
        headers=exc.headers,
    )


def rate_limit_headers(*, limit: int | None, remaining: int, reset_seconds: int) -> dict[str, str]:
    """The X-RateLimit-* headers; without a known limit only the remaining and reset."""
    headers = {
        RATE_LIMIT_REMAINING_HEADER: str(remaining),
        RATE_LIMIT_RESET_HEADER: str(reset_seconds),
    }
    if limit is not None:
        headers[RATE_LIMIT_LIMIT_HEADER] = str(limit)
    return headers


def _status_for(exc: AppError) -> HTTPStatus:
    for error_type, status in _STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            return status
    return HTTPStatus.INTERNAL_SERVER_ERROR


def _log_rejection(status: int, code: ErrorCode) -> None:
    # Expected client errors: no traceback. Security-relevant ones are warnings.
    security_relevant = status in {
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.TOO_MANY_REQUESTS,
    }
    log = logger.warning if security_relevant else logger.info
    log("request_rejected", status=status, code=code)


def _request_id(request: Request) -> str | None:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else None
