"""Typed settings of the runner, read once from environment variables at startup.

Role: `RunnerSettings`, all settings of the runner (the broker connection and logging).
Used by: `runner.main`; tests/integration/test_runner_lifecycle.py and
  tests/unit/test_env_example.py.
Depends on: `common_lib.settings.BrokerSettings`.
Key invariants: no database settings, because the runner has no database (template_core D-011).
  Settings of the job handlers (judges, timeouts) arrive with them in slice 003 (D-006).
"""

from common_lib.settings import BrokerSettings


class RunnerSettings(BrokerSettings):
    """All settings of the runner. It has no database settings: it has no database.

    Settings of the job handlers (judges, timeouts) arrive with them in slice 003.
    """
