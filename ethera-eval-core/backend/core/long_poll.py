"""The per-replica cap on concurrent long polls per user.

Role: `ConcurrentPollLimiter` — each waiting poll holds an open HTTP request and an asyncio task
  in this process; the cap protects the process from one user opening many of them.
Used by: no production code yet — generic machinery wired in slice 003 (D-006); exercised by
  tests/unit/backend/test_long_poll.py and tests/integration/test_long_polling.py.
Depends on: `common_lib.errors` (`RateLimitExceededError`, `ErrorCode.TOO_MANY_CONCURRENT_POLLS`).
Key invariants: kept in memory on purpose and applied per replica, so across the deployment a
  user may hold up to cap x replicas (template_core D-009); the request rate limit itself is the
  shared one in PostgreSQL. Over the cap is a 429 with a one-second Retry-After.
"""

import contextlib
from collections import Counter
from collections.abc import Iterator
from uuid import UUID

from common_lib.errors import ErrorCode, RateLimitExceededError

RETRY_AFTER_SECONDS = 1


class ConcurrentPollLimiter:
    def __init__(self, max_per_user: int) -> None:
        self._max_per_user = max_per_user
        self._active: Counter[UUID] = Counter()

    @contextlib.contextmanager
    def slot(self, user_id: UUID) -> Iterator[None]:
        """Hold one of the user's slots for the duration of a waiting poll."""
        if self._active[user_id] >= self._max_per_user:
            raise RateLimitExceededError(
                RETRY_AFTER_SECONDS,
                f"At most {self._max_per_user} polls may wait at the same time.",
                code=ErrorCode.TOO_MANY_CONCURRENT_POLLS,
            )
        self._active[user_id] += 1
        try:
            yield
        finally:
            self._active[user_id] -= 1
            if not self._active[user_id]:
                del self._active[user_id]
