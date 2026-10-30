"""Startup seeding of permissions, roles and the admin account.

Role: re-exports `AdminAccount`, `SeedingService` and `build_seeding_service` as the feature's
  public surface.
Used by: `backend.main` (the startup lifespan); tests/unit/backend/test_seeding_service.py.
Depends on: `backend.services.seeding.service`.
Key invariants: none.
"""

from backend.services.seeding.service import AdminAccount, SeedingService, build_seeding_service

__all__ = ["AdminAccount", "SeedingService", "build_seeding_service"]
