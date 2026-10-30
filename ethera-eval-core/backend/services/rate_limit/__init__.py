"""Rate limiting of API requests.

Role: re-exports the limiter, its rule and status types and `build_rate_limiter` as the
  feature's public surface.
Used by: `backend.main` (rules, cleanup task), `backend.api.dependencies.rate_limit`,
  `backend.api.dependencies.services`; tests/unit/backend/test_rate_limiter.py.
Depends on: `backend.services.rate_limit.service`.
Key invariants: none.
"""

from backend.services.rate_limit.service import (
    RateLimiter,
    RateLimitRule,
    RateLimitRules,
    RateLimitStatus,
    build_rate_limiter,
)

__all__ = [
    "RateLimitRule",
    "RateLimitRules",
    "RateLimitStatus",
    "RateLimiter",
    "build_rate_limiter",
]
