"""Database configuration derived from the settings.

Role: pins backend.core.database `tortoise_config` and backend.core.settings
  `DatabaseSettings`: pool size and credentials from the settings, models and migrations in one
  app (`APP_LABEL`, `MIGRATIONS_MODULE`), UTC, a bounded pool defaulting to ten, a required
  password.
Used by: pytest (unit).
Depends on: the autouse `_required_environment` from tests/unit/backend/conftest.py;
  `monkeypatch` for environment overrides. No services.
Key invariants: only builds configuration, never connects.
"""

import pytest
from pydantic import ValidationError

from backend.core.database import APP_LABEL, MIGRATIONS_MODULE, tortoise_config
from backend.core.settings import DatabaseSettings


def test_pool_size_and_credentials_come_from_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "7")

    config = tortoise_config(DatabaseSettings())

    credentials = config["connections"]["default"]["credentials"]
    assert credentials["maxsize"] == 7
    assert credentials["database"] == "unit_tests"
    assert credentials["password"] == "test-only-not-a-secret"


def test_models_and_migrations_belong_to_one_app() -> None:
    config = tortoise_config(DatabaseSettings())

    app = config["apps"][APP_LABEL]
    assert app["models"] == ["common_lib.models"]
    assert app["migrations"] == MIGRATIONS_MODULE
    assert config["use_tz"] is True
    assert config["timezone"] == "UTC"


def test_default_pool_size_is_ten() -> None:
    assert DatabaseSettings().db_pool_max_size == 10


@pytest.mark.parametrize("size", ["0", "101"])
def test_pool_size_is_bounded(monkeypatch: pytest.MonkeyPatch, size: str) -> None:
    monkeypatch.setenv("DB_POOL_MAX_SIZE", size)

    with pytest.raises(ValidationError, match="db_pool_max_size"):
        DatabaseSettings()


def test_missing_database_password_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_PASSWORD")

    with pytest.raises(ValidationError, match="db_password"):
        DatabaseSettings()
