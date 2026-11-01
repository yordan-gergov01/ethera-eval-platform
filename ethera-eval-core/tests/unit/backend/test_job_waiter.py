"""The job waiter's bookkeeping, without a database.

Role: pins backend.core.job_waiter `JobWaiter`'s in-process bookkeeping: a notification wakes
  only the waiters of its job, waiters are removed when they stop watching, a payload that is
  not a job id is ignored, `wake_all` wakes everyone.
Used by: pytest (unit).
Depends on: backend.core.settings `DatabaseSettings` with fake values; notifications are
  delivered by calling the listener callback directly. No services.
Key invariants: never connects to PostgreSQL; the LISTEN/NOTIFY path itself is covered by
  tests/integration/test_job_waiter.py.
"""

from uuid import UUID

from pydantic import SecretStr

from backend.core.job_waiter import JobWaiter
from backend.core.settings import DatabaseSettings

JOB = UUID("00000000-0000-4000-8000-0000000000aa")
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")


def waiter() -> JobWaiter:
    return JobWaiter(
        DatabaseSettings(
            db_name="unit_tests",
            db_user="unit_tests",
            db_password=SecretStr("test-only"),
            db_owner_user="unit_tests_owner",
            db_owner_password=SecretStr("test-only"),
        )
    )


def test_a_notification_wakes_only_the_waiters_of_that_job() -> None:
    jobs = waiter()
    with jobs.watch(JOB) as mine, jobs.watch(JOB) as also_mine, jobs.watch(OTHER) as other:
        jobs._on_notification(None, 0, "job_events", str(JOB))

        assert mine.is_set()
        assert also_mine.is_set()
        assert not other.is_set()


def test_waiters_are_removed_when_they_stop_watching() -> None:
    jobs = waiter()
    with jobs.watch(JOB) as event:
        pass

    jobs.notify(JOB)

    assert not event.is_set()
    assert jobs._waiters == {}


def test_a_payload_that_is_not_a_job_id_is_ignored() -> None:
    jobs = waiter()
    with jobs.watch(JOB) as event:
        jobs._on_notification(None, 0, "job_events", "not-a-uuid")

        assert not event.is_set()


def test_wake_all_wakes_every_waiter() -> None:
    jobs = waiter()
    with jobs.watch(JOB) as first, jobs.watch(OTHER) as second:
        jobs.wake_all()

        assert first.is_set()
        assert second.is_set()
