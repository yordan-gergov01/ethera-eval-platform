"""Configuration entry point for the `tortoise` migration command line, modules included.

Role: gives `tortoise makemigrations` / `sqlmigrate` the core app plus every mounted module's
  app, so a module's migrations are generated into its own package (docs/DECISIONS.md D-007).
Used by: `[tool.tortoise]` in pyproject.toml.
Depends on: the `backend` barrel, `evals.MODULES`, `common_lib.settings.load_settings`.
Key invariants: only the `DB_*` variables are required, so schema changes can be generated
  against the test database without the rest of the backend's settings.
"""

from backend import DatabaseSettings, tortoise_config
from common_lib.settings import load_settings
from evals.MODULES import MODULES

TORTOISE_ORM = tortoise_config(load_settings(DatabaseSettings), MODULES)
