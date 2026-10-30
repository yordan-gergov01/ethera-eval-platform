"""Service health checks.

Role: re-exports `HealthService` and `build_health_service` as the feature's public surface.
Used by: `backend.api.health`; tests/unit/backend/test_health.py.
Depends on: `backend.services.health.service`.
Key invariants: none.
"""

from backend.services.health.service import HealthService, build_health_service

__all__ = ["HealthService", "build_health_service"]
