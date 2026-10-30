"""Rate limiting with a sliding window counter.

Role: `RateLimiter.check` judges a request by an estimate of the requests in the last full window
  length — all of the current window plus the part of the previous window that still overlaps
  it, `estimate = previous * (1 - elapsed / window) + current` — and computes Retry-After and
  the X-RateLimit-* status; `delete_expired_windows` cleans up.
Used by: `backend.services.rate_limit` (re-export), and through it `backend.main` and the API
  rate limit dependencies.
Depends on: `backend.dal.rate_limit` (behind the `CounterStore` Protocol),
  `common_lib.errors.RateLimitExceededError`.
Key invariants: the sliding estimate avoids the double burst a plain fixed window allows at its
  edges. Rejected requests are counted too, so a client that keeps sending stays limited
  (template_core D-008). Retry-After is at least one second. The cleanup keeps two window lengths
  of the longest rule and is safe to run on every replica.
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import structlog

from backend.dal.rate_limit import RateLimitRepository, WindowCounts
from common_lib.errors import RateLimitExceededError

logger = structlog.get_logger(__name__)

Clock = Callable[[], float]


class CounterStore(Protocol):
    async def increment(
        self, key: str, *, window_start: int, window_seconds: int
    ) -> WindowCounts: ...

    async def delete_windows_before(self, window_start: int) -> int: ...


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """At most `requests` per `window_seconds` for each key."""

    name: str
    requests: int
    window_seconds: int


@dataclass(frozen=True, slots=True)
class RateLimitRules:
    """The configured rules: one for every API request, a stricter one for login."""

    default: RateLimitRule
    login: RateLimitRule


@dataclass(frozen=True, slots=True)
class RateLimitStatus:
    """What a client may still do under one rule, for the X-RateLimit-* headers."""

    limit: int
    remaining: int
    # Seconds until the current fixed window ends; approximate, because the sliding
    # estimate keeps part of the previous window for a while after that.
    reset_seconds: int


class RateLimiter:
    def __init__(self, store: CounterStore, clock: Clock = time.time) -> None:
        self._store = store
        self._clock = clock

    async def check(self, rule: RateLimitRule, key: str) -> RateLimitStatus:
        """Count one request for `key` under `rule`, or raise if it is over the limit."""
        now = self._clock()
        window = rule.window_seconds
        window_start = int(now // window) * window
        elapsed = now - window_start
        counts = await self._store.increment(
            f"{rule.name}:{key}", window_start=window_start, window_seconds=window
        )

        estimate = counts.previous * (1 - elapsed / window) + counts.current
        if estimate > rule.requests:
            retry_after = max(1, math.ceil(_seconds_until_allowed(rule, counts, elapsed=elapsed)))
            logger.warning("rate_limited", rule=rule.name, key=key, retry_after_seconds=retry_after)
            raise RateLimitExceededError(retry_after_seconds=retry_after, limit=rule.requests)

        return RateLimitStatus(
            limit=rule.requests,
            remaining=max(0, math.floor(rule.requests - estimate)),
            reset_seconds=max(1, math.ceil(window - elapsed)),
        )

    async def delete_expired_windows(self, rules: RateLimitRules) -> int:
        """Delete the windows no rule reads any more; safe to run on every replica.

        A rule reads its current and its previous window, which together start no
        earlier than two window lengths ago.
        """
        longest = max(rules.default.window_seconds, rules.login.window_seconds)
        deleted = await self._store.delete_windows_before(int(self._clock()) - 2 * longest)
        logger.debug("rate_limit_windows_deleted", count=deleted)
        return deleted


def _seconds_until_allowed(rule: RateLimitRule, counts: WindowCounts, *, elapsed: float) -> float:
    """How long until one more request would fit, if the client sends nothing meanwhile."""
    window = rule.window_seconds
    room = rule.requests - counts.current - 1
    if room >= 0:
        # The current window has room; wait until enough of the previous one has slid out.
        if counts.previous == 0:
            return 0.0
        return max(0.0, window * (1 - room / counts.previous) - elapsed)
    # The current window alone is full: wait for the next one, in which the current
    # count becomes the previous one and slides out the same way.
    return (window - elapsed) + max(0.0, window * (1 - (rule.requests - 1) / counts.current))


def build_rate_limiter(clock: Clock = time.time) -> RateLimiter:
    """Wire the limiter to the shared PostgreSQL counters."""
    return RateLimiter(store=RateLimitRepository(), clock=clock)
