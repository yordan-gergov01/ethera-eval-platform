"""Suite-wide fixtures: the logging configuration is undone after every test.

Role: shared fixture for the whole suite; undoes what building an application
  (`backend.main.create_app` calling common_lib.logging_config `configure_logging`) leaves behind.
Used by: pytest, autouse for every test under tests/ (unit, integration and architecture).
Depends on: `structlog` and the stdlib root logger; no services.
Key invariants: after each test the structlog context and defaults are reset and the root
  handlers cleared, so no handler bound to a stdout pytest has replaced writes to a closed stream.
"""

import logging
from collections.abc import Iterator

import pytest
import structlog


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    """Undo logging configuration after each test.

    Building an application configures logging with a handler bound to the current
    stdout. Pytest replaces stdout per test, so a handler left behind would write
    to a closed stream in the next test.
    """
    yield
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()
