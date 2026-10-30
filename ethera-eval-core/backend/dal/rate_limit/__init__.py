"""Data access for rate limit counters.

Role: re-exports `RateLimitRepository` and `WindowCounts` as the feature's public surface.
Used by: `backend.services.rate_limit.service`; tests/integration/test_rate_limit_store.py and
  tests/unit/backend/test_rate_limiter.py.
Depends on: `backend.dal.rate_limit.repository`.
Key invariants: none.
"""

from backend.dal.rate_limit.repository import RateLimitRepository, WindowCounts

__all__ = ["RateLimitRepository", "WindowCounts"]
