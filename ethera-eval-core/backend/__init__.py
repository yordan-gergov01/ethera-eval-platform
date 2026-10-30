"""The platform core's barrel: the only door through which domain modules reach the core.

Role: re-exports what `evals` may use from the core — the app factory, the module-mount type,
  and the database configuration the migration command line needs. Appended to, never edited,
  as modules need more (auth dependencies, audit, spend arrive with their first callers).
Used by: `evals.app`, `evals.MODULES`, `evals.migration_cli`.
Depends on: `backend.main`, `backend.core.modules`, `backend.core.database`,
  `backend.core.settings`.
Key invariants: `evals` imports `backend` only through this module (import-linter contract
  "The domain reaches the core only through its barrel"); nothing in `backend` imports
  `evals` (tests/integration/test_boot_without_evals.py).
"""

from backend.core.database import tortoise_config
from backend.core.modules import ModuleMount
from backend.core.settings import BackendSettings, DatabaseSettings
from backend.main import create_app

__all__ = [
    "BackendSettings",
    "DatabaseSettings",
    "ModuleMount",
    "create_app",
    "tortoise_config",
]
