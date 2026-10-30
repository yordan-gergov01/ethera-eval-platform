"""The per-replica cap on concurrent long polls per user, without a database.

Role: pins backend.core.long_poll `ConcurrentPollLimiter`: a poll beyond the per-user cap is
  refused with TOO_MANY_CONCURRENT_POLLS and `RETRY_AFTER_SECONDS`, other users are unaffected,
  and a slot is released when its poll ends, even by an error.
Used by: pytest (unit).
Depends on: common_lib.errors `RateLimitExceededError`; no fixtures or services.
Key invariants: the refusal carries no request-rate `limit`, so the X-RateLimit-* headers keep
  describing the request rate limit; the HTTP path is covered by
  tests/integration/test_long_polling.py.
"""

from uuid import UUID

import pytest

from backend.core.long_poll import RETRY_AFTER_SECONDS, ConcurrentPollLimiter
from common_lib.errors import ErrorCode, RateLimitExceededError

DORA = UUID("00000000-0000-4000-8000-0000000000aa")
ERIC = UUID("00000000-0000-4000-8000-0000000000bb")


def test_a_poll_beyond_the_cap_is_refused_and_other_users_are_unaffected() -> None:
    limiter = ConcurrentPollLimiter(max_per_user=3)
    with limiter.slot(DORA), limiter.slot(DORA), limiter.slot(DORA):
        with pytest.raises(RateLimitExceededError) as refused, limiter.slot(DORA):
            pass
        with limiter.slot(ERIC):
            pass

    assert refused.value.code is ErrorCode.TOO_MANY_CONCURRENT_POLLS
    assert refused.value.retry_after_seconds == RETRY_AFTER_SECONDS == 1
    # Not the request rate limit: the X-RateLimit-* headers keep describing that one.
    assert refused.value.limit is None


def test_a_slot_is_released_when_the_poll_ends_even_by_an_error() -> None:
    limiter = ConcurrentPollLimiter(max_per_user=1)
    with pytest.raises(RuntimeError), limiter.slot(DORA):
        raise RuntimeError("the poll failed")

    with limiter.slot(DORA):
        pass

    assert limiter._active == {}
