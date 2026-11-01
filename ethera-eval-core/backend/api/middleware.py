"""ASGI middleware that wraps every HTTP request.

Role: request ID and access log, X-RateLimit-* headers, the generic 500, and the body size
  limit. Order, outermost first (see `backend.main`):
    ProxyHeadersMiddleware     client address from trusted proxies (only if configured)
    RequestContextMiddleware   request ID, log context, access log line
    CORSMiddleware             CORS headers on every response below it
    RateLimitHeadersMiddleware X-RateLimit-* headers from the request's rate limit status
    UnhandledErrorMiddleware   unexpected exception -> logged once, generic 500
    BodySizeLimitMiddleware    oversized body -> 413
Used by: `backend.main` (installs them); `backend.api.dependencies.rate_limit` reads
  `RATE_LIMIT_STATE_KEY`.
Depends on: `backend.api.errors` (problem responses, rate limit headers),
  `common_lib.request_id`, `common_lib.errors.ErrorCode`, Starlette's ASGI types.
Key invariants: everything a client can receive, including a 500 or a 413, is produced inside
  CORS, so a browser can read the status and the request ID. An unhandled exception is logged
  exactly once, by the type names of its chain only: exception messages and tracebacks can
  carry SQL bound parameters and other user data (observability.md never-log list; this
  narrows template_core D-005). Log lines name the matched route template, never the raw path,
  and no path at all when no route matched (FIX-003,
  `test_unhandled_errors_log_neither_raw_paths_nor_exception_text`). An incoming X-Request-ID is
  reused only if valid. A 429 keeps its own rate limit headers. `/health` access lines are
  debug-level so they do not drown everything else.
"""

import time
from http import HTTPStatus

import structlog
from fastapi import HTTPException
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.api.errors import (
    PAYLOAD_TOO_LARGE_DETAIL,
    RATE_LIMIT_LIMIT_HEADER,
    exception_chain,
    internal_error_response,
    problem_response,
    rate_limit_headers,
)
from common_lib.errors import ErrorCode
from common_lib.request_id import REQUEST_ID_HEADER, is_valid_request_id, new_request_id

access_logger = structlog.get_logger("backend.access")
logger = structlog.get_logger(__name__)

# Key in the request state under which the rate limit dependencies leave the status
# of the most restrictive rule that applied.
RATE_LIMIT_STATE_KEY = "rate_limit_status"

# Health checks run every few seconds; their access lines would drown everything else.
_QUIET_PATHS = frozenset({"/health"})


class RequestContextMiddleware:
    """Gives every request an ID, binds it to the log context, and writes one access line.

    A valid incoming `X-Request-ID` is reused so a caller can correlate its own logs;
    otherwise a new ID is generated. The ID is returned in the response header and is
    available as `request.state.request_id`.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or new_request_id()
        scope.setdefault("state", {})["request_id"] = request_id
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                await self.app(scope, receive, send_with_request_id)
            finally:
                log = access_logger.debug if scope["path"] in _QUIET_PATHS else access_logger.info
                log(
                    "request",
                    method=scope["method"],
                    **_route_fields(scope),
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )


class RateLimitHeadersMiddleware:
    """Adds the X-RateLimit-* headers to every response of a rate-limited request.

    The rate limit dependencies record their result in the request state; this turns
    it into headers on the way out, so error responses after the check (401, 404,
    422, ...) carry them too. A 429 already has its own headers and is left alone.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                status = scope.get("state", {}).get(RATE_LIMIT_STATE_KEY)
                headers = MutableHeaders(scope=message)
                if status is not None and RATE_LIMIT_LIMIT_HEADER not in headers:
                    for name, value in rate_limit_headers(
                        limit=status.limit,
                        remaining=status.remaining,
                        reset_seconds=status.reset_seconds,
                    ).items():
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


class UnhandledErrorMiddleware:
    """Turns an exception no handler caught into a generic 500.

    The exception is logged once, by the type names of its chain, with the request
    context. Without this, Starlette's outermost error handler would answer outside
    CORS and the request context, and the server would log the traceback again.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            # Type names only: the message and traceback text may hold bound parameters.
            logger.error(
                "unhandled_exception",
                method=scope["method"],
                **_route_fields(scope),
                error_type=type(exc).__name__,
                error_chain=exception_chain(exc),
            )
            if response_started:
                # Headers are already sent; the connection is closed by the server.
                return
            response = internal_error_response(
                instance=scope["path"], request_id=_request_id_from_scope(scope)
            )
            await response(scope, receive, send)


class BodySizeLimitMiddleware:
    """Rejects request bodies larger than `max_bytes` with 413.

    A declared `Content-Length` above the limit is rejected before the body is read.
    A body without a length (chunked) is counted while it is read; FastAPI passes its
    own HTTPException through body parsing unchanged, so the error handlers render it.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            response = problem_response(
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                code=ErrorCode.PAYLOAD_TOO_LARGE,
                detail=PAYLOAD_TOO_LARGE_DETAIL,
                instance=scope["path"],
                request_id=_request_id_from_scope(scope),
            )
            await response(scope, receive, send)
            return

        received = 0

        async def receive_limited() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return message

        await self.app(scope, receive_limited, send)


def _route_fields(scope: Scope) -> dict[str, str]:
    """The matched route's template as `path`; nothing when no route matched."""
    template = getattr(scope.get("route"), "path", None)
    return {"path": template} if isinstance(template, str) else {}


def _incoming_request_id(scope: Scope) -> str | None:
    header = REQUEST_ID_HEADER.lower().encode()
    for name, value in scope["headers"]:
        if name == header:
            candidate = value.decode("latin-1")
            return candidate if is_valid_request_id(candidate) else None
    return None


def _request_id_from_scope(scope: Scope) -> str | None:
    request_id = scope.get("state", {}).get("request_id")
    return request_id if isinstance(request_id, str) else None


def _content_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
