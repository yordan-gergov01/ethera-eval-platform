"""Backend unit-test fixtures: the required environment, so the backend settings load.

Role: autouse fixture that sets every required backend setting (database, JWT secret, admin
  account, broker) to a fake value for backend.core.settings (the key is `TEST_JWT_SECRET`).
Used by: pytest, autouse for every test in tests/unit/backend/.
Depends on: pytest's `monkeypatch`; no services.
Key invariants: all values are fake test values; unit tests never connect to a database or
  broker.
"""

import pytest

TEST_JWT_SECRET = "test-only-not-a-secret-signing-key-32-bytes-long"


@pytest.fixture(autouse=True)
def _required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required settings, so the backend settings load; unit tests never connect."""
    monkeypatch.setenv("DB_NAME", "unit_tests")
    monkeypatch.setenv("DB_USER", "unit_tests")
    monkeypatch.setenv("DB_PASSWORD", "test-only-not-a-secret")
    monkeypatch.setenv("DB_OWNER_USER", "unit_tests_owner")
    monkeypatch.setenv("DB_OWNER_PASSWORD", "test-only-not-a-secret-owner")
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-only-admin-password")
    monkeypatch.setenv("RABBITMQ_VHOST", "unit_tests")
    monkeypatch.setenv("RABBITMQ_USER", "unit_tests")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "test-only-not-a-secret")
