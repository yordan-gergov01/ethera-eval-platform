"""How the worker turns every outcome of a handler into a result, without a broker.

Role: pins runner.worker `JobWorker.answer`: a handler's answer becomes a completed result with
  its duration logged, a timeout or a bug becomes a failed result with its `JobErrorCode`, and
  payload types must match their queues.
Used by: pytest (unit).
Depends on: `EchoHandler`, `Ping`/`Pong`, `ping` from tests/job_payloads.py; a local `StepClock`;
  a `log_lines` fixture over common_lib.logging_config `configure_logging`; the autouse
  `_required_environment` from tests/unit/runner/conftest.py.
Key invariants: runs on test-local payloads (docs/DECISIONS.md D-006); an unexpected error is
  logged with its traceback but its message never reaches the result; durations come from the
  step clock, so they are exact.
"""

import io
import json
import logging
from collections.abc import Iterator

import pytest
import structlog

from common_lib.logging_config import configure_logging
from common_lib.messaging.jobs import JobErrorCode, JobResultStatus
from runner.worker import JobWorker
from tests.job_payloads import EchoHandler, Ping, Pong, ping


class StepClock:
    """Each reading is 0.25 seconds after the previous one."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.25
        return self.now


def worker(handler: EchoHandler, timeout: float = 5) -> JobWorker[Ping, Pong]:
    return JobWorker(
        handler,
        request_type=Ping,
        result_type=Pong,
        handler_timeout_seconds=timeout,
        prefetch_count=1,
        clock=StepClock(),
    )


@pytest.fixture
def log_lines() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    configure_logging(service="test", stream=stream)
    yield stream
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


def events(stream: io.StringIO, name: str) -> list[dict[str, object]]:
    return [e for e in map(json.loads, stream.getvalue().splitlines()) if e["event"] == name]


async def test_an_answer_is_the_handlers_result(log_lines: io.StringIO) -> None:
    request = ping("Hello")

    result = await worker(EchoHandler()).answer(request)

    assert (result.job_id, result.status) == (request.job_id, JobResultStatus.COMPLETED)
    assert (result.text, result.error_code) == ("echo: Hello", None)
    [answered] = events(log_lines, "job_answered")
    assert answered["duration_ms"] == 250


@pytest.mark.parametrize(
    ("handler", "code"),
    [
        (EchoHandler(delay=1), JobErrorCode.HANDLER_TIMEOUT),
        (EchoHandler(error=KeyError("unexpected")), JobErrorCode.INTERNAL_ERROR),
    ],
    ids=["timeout", "bug"],
)
async def test_every_failure_becomes_a_failed_result_with_its_code(
    handler: EchoHandler, code: JobErrorCode
) -> None:
    request = ping()

    result = await worker(handler, timeout=0.1).answer(request)

    assert (result.status, result.error_code, result.text) == (JobResultStatus.FAILED, code, None)
    assert result.job_id == request.job_id


async def test_an_unexpected_error_is_logged_with_its_traceback_but_not_returned(
    log_lines: io.StringIO,
) -> None:
    result = await worker(EchoHandler(error=KeyError("unexpected"))).answer(ping())

    [failure] = events(log_lines, "job_failed")
    assert failure["error_code"] == "INTERNAL_ERROR"
    assert "KeyError" in json.dumps(failure["exception"])
    assert "unexpected" not in result.model_dump_json()


@pytest.mark.parametrize(
    ("request_type", "result_type"), [(Pong, Pong), (Ping, Ping)], ids=["request", "result"]
)
def test_payload_types_must_match_their_queues(
    request_type: type[Ping], result_type: type[Pong]
) -> None:
    with pytest.raises(ValueError, match="carries"):
        JobWorker(
            EchoHandler(),
            request_type=request_type,
            result_type=result_type,
            handler_timeout_seconds=1,
            prefetch_count=1,
        )
