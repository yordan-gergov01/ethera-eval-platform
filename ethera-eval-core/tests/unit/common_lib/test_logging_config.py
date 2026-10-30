"""One logging pipeline: JSON lines with context, redaction, structured tracebacks.

Role: pins common_lib.logging_config `configure_logging`: JSON lines with the standard fields,
  context variables on every line, stdlib and uvicorn logs through the same pipeline, sensitive
  values `REDACTED` at any depth, structured tracebacks, level filtering, quiet library SQL at
  debug, and a human-readable console format.
Used by: pytest (unit).
Depends on: the local `stream` fixture, which configures logging into a `StringIO` and resets
  structlog and the root handlers afterwards. No services.
Key invariants: tracebacks never contain frame locals, in JSON or console format, so secrets
  held in local variables cannot leak into the logs.
"""

import io
import json
import logging
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import pytest
import structlog

from common_lib.logging_config import REDACTED, configure_logging


@pytest.fixture
def stream() -> Iterator[io.StringIO]:
    output = io.StringIO()
    configure_logging(service="test-service", level="INFO", log_format="json", stream=output)
    yield output
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


def lines(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_json_line_has_the_standard_fields(stream: io.StringIO) -> None:
    structlog.get_logger("example").info("job_published", job_id="j-1")

    [line] = lines(stream)
    assert line["event"] == "job_published"
    assert line["level"] == "info"
    assert line["logger"] == "example"
    assert line["service"] == "test-service"
    assert line["job_id"] == "j-1"
    assert datetime.fromisoformat(line["timestamp"]).utcoffset() is not None


def test_context_variables_appear_on_every_line(stream: io.StringIO) -> None:
    with structlog.contextvars.bound_contextvars(request_id="req-42"):
        structlog.get_logger("example").info("first")
        logging.getLogger("library").warning("second")

    assert [line["request_id"] for line in lines(stream)] == ["req-42", "req-42"]


def test_standard_library_logs_use_the_same_pipeline(stream: io.StringIO) -> None:
    logging.getLogger("uvicorn.error").info("Application startup complete.")

    [line] = lines(stream)
    assert line["event"] == "Application startup complete."
    assert line["logger"] == "uvicorn.error"
    assert line["service"] == "test-service"


def test_uvicorn_colour_copy_of_the_message_is_dropped(stream: io.StringIO) -> None:
    logging.getLogger("uvicorn.error").info(
        "Started server process [%d]", 7, extra={"color_message": "Started \x1b[36m%d\x1b[0m"}
    )

    [line] = lines(stream)
    assert line["event"] == "Started server process [7]"
    assert "color_message" not in line


def test_sensitive_values_are_redacted_at_any_depth(stream: io.StringIO) -> None:
    structlog.get_logger("example").info(
        "login_attempt",
        username="alice",
        password="hunter2-but-longer",
        headers={"Authorization": "Bearer abc.def.ghi", "accept": "json"},
    )

    [line] = lines(stream)
    assert line["username"] == "alice"
    assert line["password"] == REDACTED
    assert line["headers"] == {"Authorization": REDACTED, "accept": "json"}
    assert "hunter2" not in stream.getvalue()
    assert "abc.def.ghi" not in stream.getvalue()


def test_exceptions_are_rendered_as_structured_tracebacks(stream: io.StringIO) -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        structlog.get_logger("example").exception("job_failed")

    [line] = lines(stream)
    [exception] = line["exception"]
    assert exception["exc_type"] == "ValueError"
    assert exception["exc_value"] == "boom"
    assert exception["frames"]


def test_tracebacks_never_contain_frame_locals(stream: io.StringIO) -> None:
    authorization = "Bearer must-not-be-logged"  # a local variable of this frame

    try:
        raise RuntimeError("failed")
    except RuntimeError:
        structlog.get_logger("example").exception("request_failed")

    [line] = lines(stream)
    assert all("locals" not in frame for frame in line["exception"][0]["frames"])
    assert authorization not in stream.getvalue()


def test_console_tracebacks_never_contain_frame_locals() -> None:
    output = io.StringIO()
    configure_logging(service="test-service", level="INFO", log_format="console", stream=output)
    authorization = "Bearer must-not-be-logged"  # a local variable of this frame

    try:
        raise RuntimeError("failed")
    except RuntimeError:
        structlog.get_logger("example").exception("request_failed")

    assert "RuntimeError: failed" in output.getvalue()
    assert authorization not in output.getvalue()


def test_level_filters_lower_lines(stream: io.StringIO) -> None:
    structlog.get_logger("example").debug("noise")

    assert stream.getvalue() == ""


def test_library_sql_logging_stays_quiet_at_debug() -> None:
    output = io.StringIO()
    configure_logging(service="test-service", level="DEBUG", log_format="json", stream=output)

    logging.getLogger("tortoise.db_client").debug("SELECT ... with parameters")

    assert output.getvalue() == ""
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


def test_console_format_is_human_readable() -> None:
    output = io.StringIO()
    configure_logging(service="test-service", level="INFO", log_format="console", stream=output)

    structlog.get_logger("example").info("hello", user_id="u-1")

    text = output.getvalue()
    assert "hello" in text
    assert "user_id=u-1" in text
    assert not text.startswith("{")
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()
