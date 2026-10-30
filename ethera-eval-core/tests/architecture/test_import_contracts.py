"""The import-linter contracts in pyproject.toml hold for the whole code base.

Role: runs the `[tool.importlinter]` contracts (for example: the backend and the runner do not
  import each other) as a test, so a forbidden import fails the suite.
Used by: pytest (architecture guard).
Depends on: import-linter's `lint_imports` over pyproject.toml; the local
  `_keep_loggers_enabled` fixture. No services.
Key invariants: import-linter runs without its cache (`no_cache=True`); loggers that its
  `dictConfig` call disables are re-enabled afterwards, so later tests still see log output.
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from importlinter.cli import EXIT_STATUS_SUCCESS, lint_imports

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


@pytest.fixture
def _keep_loggers_enabled() -> Iterator[None]:
    """Undo the side effect of import-linter's logging setup on existing loggers.

    It calls `logging.config.dictConfig`, which disables every logger that already
    exists (`disable_existing_loggers` defaults to true). Later tests would then see
    no output from loggers such as uvicorn's.
    """
    enabled = [
        logger
        for logger in logging.root.manager.loggerDict.values()
        if isinstance(logger, logging.Logger) and not logger.disabled
    ]
    yield
    for logger in enabled:
        logger.disabled = False


@pytest.mark.usefixtures("_keep_loggers_enabled")
def test_import_contracts_hold() -> None:
    assert lint_imports(config_filename=str(PYPROJECT), no_cache=True) == EXIT_STATUS_SUCCESS
