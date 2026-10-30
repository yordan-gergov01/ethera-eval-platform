"""The composition root: the platform core with every domain module mounted.

Role: the backend's production entry point
  (`uvicorn evals.app:create_app --factory`); it wraps the core's factory and passes it
  `evals.MODULES`.
Used by: `backend/Dockerfile` (runtime CMD) and the integration tests that need the whole app.
Depends on: the `backend` barrel and `evals.MODULES`.
Key invariants: lives outside `backend/`, so the core never names a domain module; the core
  alone (`backend.main:create_app`) stays a complete, bootable app
  (tests/integration/test_boot_without_evals.py).
"""

from fastapi import FastAPI

from backend import BackendSettings
from backend import create_app as create_core_app
from evals.MODULES import MODULES


def create_app(settings: BackendSettings | None = None) -> FastAPI:
    """The backend with every module in `evals.MODULES` mounted."""
    return create_core_app(settings, modules=MODULES)
