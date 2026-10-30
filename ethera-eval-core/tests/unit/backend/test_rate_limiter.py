"""Sliding window rate limiter with an in-memory store and a controlled clock.

Role: pins backend.services.rate_limit `RateLimiter`: requests up to the limit pass with the
  right remaining and reset values, keys and rules count separately, rejected requests count
  too, the previous window slides out, Retry-After is exact, rejections are logged, and the
  cleanup keeps every window a rule still reads.
Used by: pytest (unit).
Depends on: local `MemoryStore` (the PostgreSQL store's behaviour, for unit tests only),
  `FakeClock`, and a `log_lines` fixture over common_lib.logging_config `configure_logging`.
  No services.
Key invariants: time is a controlled clock, never the wall clock; each Retry-After is proved
  exact by probing one second before (still refused) and at it (allowed); the real store is
  covered by tests/integration/test_rate_limit_store.py.
"""

import io
import json
import logging
from collections import Counter
from collections.abc import Iterator

import pytest
import structlog

from backend.dal.rate_limit import WindowCounts
from backend.services.rate_limit import (
    RateLimiter,
    RateLimitRule,
    RateLimitRules,
    RateLimitStatus,
)
from common_lib.errors import RateLimitExceededError
from common_lib.logging_config import configure_logging

RULE = RateLimitRule(name="default", requests=10, window_seconds=60)


class MemoryStore:
    """The PostgreSQL store's behaviour, for unit tests only."""

    def __init__(self) -> None:
        self.counts: Counter[tuple[str, int]] = Counter()

    async def increment(self, key: str, *, window_start: int, window_seconds: int) -> WindowCounts:
        self.counts[key, window_start] += 1
        return WindowCounts(
            current=self.counts[key, window_start],
            previous=self.counts[key, window_start - window_seconds],
        )

    async def delete_windows_before(self, window_start: int) -> int:
        expired = [entry for entry in self.counts if entry[1] < window_start]
        for entry in expired:
            del self.counts[entry]
        return len(expired)


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def limiter(store: MemoryStore, clock: FakeClock) -> RateLimiter:
    return RateLimiter(store, clock=clock)


async def send(limiter: RateLimiter, times: int, key: str = "ip:a") -> list[RateLimitStatus]:
    return [await limiter.check(RULE, key) for _ in range(times)]


async def retry_after(limiter: RateLimiter, key: str = "ip:a") -> int:
    with pytest.raises(RateLimitExceededError) as raised:
        await limiter.check(RULE, key)
    return raised.value.retry_after_seconds


async def test_requests_up_to_the_limit_pass(limiter: RateLimiter, clock: FakeClock) -> None:
    clock.now = 15.0

    statuses = await send(limiter, 10)

    assert [s.remaining for s in statuses] == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    assert {(s.limit, s.reset_seconds) for s in statuses} == {(10, 45)}


async def test_one_more_is_rejected_with_the_limit(limiter: RateLimiter) -> None:
    await send(limiter, 10)

    with pytest.raises(RateLimitExceededError) as raised:
        await limiter.check(RULE, "ip:a")

    assert raised.value.limit == 10
    assert raised.value.retry_after_seconds >= 1


async def test_keys_and_rules_are_counted_separately(
    limiter: RateLimiter, store: MemoryStore
) -> None:
    await send(limiter, 10, key="ip:a")

    await limiter.check(RULE, "ip:b")
    await limiter.check(RateLimitRule(name="login", requests=5, window_seconds=60), "ip:a")

    assert store.counts == Counter(
        {("default:ip:a", 0): 10, ("default:ip:b", 0): 1, ("login:ip:a", 0): 1}
    )


async def test_rejected_requests_are_counted(limiter: RateLimiter, store: MemoryStore) -> None:
    await send(limiter, 10)
    for _ in range(3):
        await retry_after(limiter)

    assert store.counts["default:ip:a", 0] == 13


async def test_previous_window_still_counts_after_the_edge(
    limiter: RateLimiter, clock: FakeClock
) -> None:
    # A plain fixed window would allow ten more at 60 s: a burst of twenty in one second.
    clock.now = 59.0
    await send(limiter, 10)

    clock.now = 60.0
    await retry_after(limiter)


async def test_previous_window_slides_out(limiter: RateLimiter, clock: FakeClock) -> None:
    clock.now = 59.0
    await send(limiter, 10)

    # Half of the previous window still counts: 10 * 0.5 = 5, so five more fit.
    clock.now = 90.0
    statuses = await send(limiter, 5)

    assert statuses[-1].remaining == 0
    await retry_after(limiter)


async def test_retry_after_is_exact_when_the_previous_window_is_full(
    store: MemoryStore, clock: FakeClock
) -> None:
    clock.now = 59.0
    await send(RateLimiter(store, clock=clock), 10)
    clock.now = 60.0
    wait = await retry_after(RateLimiter(store, clock=clock))

    # The rejected request counts too: 10 * (1 - t/60) + 2 <= 10 from t = 12 s.
    assert wait == 12
    early, on_time = MemoryStore(), MemoryStore()
    for probe, delay, allowed in ((early, wait - 1, False), (on_time, wait, True)):
        probe.counts = store.counts.copy()
        probe_clock = FakeClock(60.0 + delay)
        check = RateLimiter(probe, clock=probe_clock).check(RULE, "ip:a")
        if allowed:
            await check
        else:
            with pytest.raises(RateLimitExceededError):
                await check


async def test_retry_after_is_exact_when_the_current_window_is_full(
    store: MemoryStore, clock: FakeClock
) -> None:
    await send(RateLimiter(store, clock=clock), 10)
    wait = await retry_after(RateLimiter(store, clock=clock))

    # Eleven counted in the first window: 11 * (1 - t/60) + 1 <= 10 from 10.9 s into the
    # next window, so 70.9 s from now.
    assert wait == 71
    for delay, allowed in ((wait - 1, False), (wait, True)):
        probe = MemoryStore()
        probe.counts = store.counts.copy()
        check = RateLimiter(probe, clock=FakeClock(float(delay))).check(RULE, "ip:a")
        if allowed:
            await check
        else:
            with pytest.raises(RateLimitExceededError):
                await check


@pytest.fixture
def log_lines() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    configure_logging(service="test", stream=stream)
    yield stream
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


async def test_rejection_is_logged(limiter: RateLimiter, log_lines: io.StringIO) -> None:
    await send(limiter, 10)
    wait = await retry_after(limiter)

    [event] = [
        e
        for e in map(json.loads, log_lines.getvalue().splitlines())
        if e["event"] == "rate_limited"
    ]
    assert (event["rule"], event["key"], event["retry_after_seconds"]) == ("default", "ip:a", wait)
    assert event["level"] == "warning"


async def test_cleanup_keeps_every_window_a_rule_still_reads(
    limiter: RateLimiter, store: MemoryStore, clock: FakeClock
) -> None:
    rules = RateLimitRules(
        default=RULE, login=RateLimitRule(name="login", requests=5, window_seconds=300)
    )
    for window_start in (0, 300, 600, 900):
        store.counts["login:ip:a", window_start] = 1
    for window_start in (840, 900, 960):
        store.counts["default:ip:a", window_start] = 1

    # At 1000 s the login rule reads 900 and 600, the default rule 960 and 900.
    clock.now = 1000.0
    deleted = await limiter.delete_expired_windows(rules)

    assert deleted == 2
    assert sorted(store.counts) == [
        ("default:ip:a", 840),
        ("default:ip:a", 900),
        ("default:ip:a", 960),
        ("login:ip:a", 600),
        ("login:ip:a", 900),
    ]
