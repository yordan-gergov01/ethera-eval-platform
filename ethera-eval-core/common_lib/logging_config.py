"""Structured logging, configured once per service at startup.

Role: `configure_logging` routes structlog and standard-library logging (uvicorn, Tortoise,
  aio-pika) through one pipeline to stdout — JSON lines in containers, readable console lines
  locally — with the sensitive-key redaction processor.
Used by: `backend.main`, `runner.main`; `common_lib.settings` (the `LogLevel` / `LogFormat`
  types); unit tests that capture logs.
Depends on: structlog, the standard `logging` module.
Key invariants: context such as the request ID is bound with `structlog.contextvars` and appears
  on every line logged while bound. Values of `SENSITIVE_KEYS` are redacted at any nesting
  depth — a safety net, not a licence to log secrets. Tracebacks are rendered without frame
  locals (they hold tokens and passwords that key-based redaction cannot see). Tortoise stays at
  WARNING whatever LOG_LEVEL says, because it logs SQL parameters at DEBUG. Uvicorn's own
  handlers are removed so each line goes through the pipeline exactly once (template_core D-005).
"""

import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any, Literal, TextIO

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

LogFormat = Literal["json", "console"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

REDACTED = "[REDACTED]"

# Keys whose values must never reach the logs. Matching is case-insensitive and
# applies at any nesting depth; it is a safety net, not a licence to log secrets.
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "current_password",
        "jwt_secret",
        "new_password",
        "password",
        "password_hash",
        "refresh_token",
        "secret",
        "set-cookie",
        "token",
    }
)

# Third-party loggers and the level they log at. Tortoise logs SQL with its
# parameters at DEBUG, so it stays at WARNING whatever LOG_LEVEL says.
LIBRARY_LOG_LEVELS: Mapping[str, int] = {
    "uvicorn": logging.INFO,
    "uvicorn.error": logging.INFO,
    "uvicorn.access": logging.WARNING,
    "tortoise": logging.WARNING,
    "asyncpg": logging.WARNING,
    "aio_pika": logging.WARNING,
    "aiormq": logging.WARNING,
    "asyncio": logging.WARNING,
    # HTTP clients log every request URL at INFO, query string included: a webhook URL or a
    # reset token would reach the logs (sealed by test_never_log).
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
}


def redact_sensitive(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """Replace the values of sensitive keys, including inside nested mappings."""
    _redact(event_dict)
    return event_dict


def _redact(mapping: MutableMapping[str, Any]) -> None:
    for key, value in mapping.items():
        if key.lower() in SENSITIVE_KEYS:
            mapping[key] = REDACTED
        elif isinstance(value, MutableMapping):
            _redact(value)


def _drop_color_message(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """Uvicorn adds a copy of its message with terminal colour codes; keep only the plain one."""
    event_dict.pop("color_message", None)
    return event_dict


def _add_service(service: str) -> Processor:
    def add_service(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", service)
        return event_dict

    return add_service


def configure_logging(
    *,
    service: str,
    level: LogLevel = "INFO",
    log_format: LogFormat = "json",
    stream: TextIO | None = None,
) -> None:
    """Route structlog and standard-library logging through one pipeline to `stream`."""
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
        _drop_color_message,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service(service),
        redact_sensitive,
    ]

    renderers: list[Processor]
    if log_format == "json":
        renderers = [
            # Tracebacks without frame locals: locals hold request headers, tokens and
            # passwords as opaque strings that key-based redaction cannot see.
            structlog.processors.ExceptionRenderer(
                structlog.tracebacks.ExceptionDictTransformer(show_locals=False)
            ),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Plain tracebacks: structlog would otherwise pick Rich when it is installed,
        # and Rich prints frame locals by default.
        renderers = [
            structlog.dev.ConsoleRenderer(
                colors=False, exception_formatter=structlog.dev.plain_traceback
            )
        ]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *renderers],
    )
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name, library_level in LIBRARY_LOG_LEVELS.items():
        library_logger = logging.getLogger(name)
        # Uvicorn installs its own handlers before the application starts; remove
        # them so its lines go through the shared pipeline exactly once.
        library_logger.handlers.clear()
        library_logger.propagate = True
        library_logger.setLevel(max(library_level, logging.getLevelName(level)))

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
