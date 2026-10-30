"""Runner unit-test fixtures: the required environment, so the runner settings load.

Role: autouse fixture that sets the required broker settings (vhost, user, password) to fake
  values for runner.settings `RunnerSettings`.
Used by: pytest, autouse for every test in tests/unit/runner/ (test_heartbeat.py,
  test_worker.py).
Depends on: pytest's `monkeypatch`; no services.
Key invariants: all values are fake test values; unit tests never connect to the broker.
"""

import pytest


@pytest.fixture(autouse=True)
def _required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required settings, so the runner settings load; unit tests never connect."""
    monkeypatch.setenv("RABBITMQ_VHOST", "unit_tests")
    monkeypatch.setenv("RABBITMQ_USER", "unit_tests")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "test-only-not-a-secret")
