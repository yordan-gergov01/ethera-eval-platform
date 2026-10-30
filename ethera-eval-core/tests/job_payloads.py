"""Test-local job payloads for the generic messaging machinery.

Role: stand-in payloads for common_lib.messaging.jobs `JobPayload`: `Ping` on the job queue,
  `Pong` on the result queue, builders (`ping`, `pong_for`, `failed_pong`) and `EchoHandler`,
  a runner handler that echoes, can be slowed or made to fail, and counts its calls.
Used by: tests/integration/test_job_publisher.py, test_job_results.py,
  test_runner_lifecycle.py, test_runner_worker.py; tests/unit/backend/test_job_consumers.py;
  tests/unit/common_lib/test_messaging_contract.py; tests/unit/runner/test_worker.py.
Depends on: common_lib.messaging.jobs (`JobPayload`, `MessageType`, `JobResultStatus`,
  `JobErrorCode`); no services.
Key invariants: the real payloads (`EvalTrialBatchRequested`, `TrialBatchCompleted`) arrive
  with slice 003 (docs/DECISIONS.md D-006), so the publisher, consumers and worker are
  exercised with these; each carries a field beyond `job_id`, so a test fails if any path
  serialises only the `JobPayload` base fields.
"""

import asyncio
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import Field

from common_lib.messaging.jobs import JobErrorCode, JobPayload, JobResultStatus, MessageType


class Ping(JobPayload):
    """Backend to runner: a request carrying some text."""

    MESSAGE_TYPE: ClassVar[MessageType] = MessageType.EVAL_TRIAL_BATCH_REQUESTED

    text: str = Field(min_length=1)


class Pong(JobPayload):
    """Runner to backend: the answer to a `Ping`, or the code it failed with."""

    MESSAGE_TYPE: ClassVar[MessageType] = MessageType.TRIAL_BATCH_COMPLETED

    status: JobResultStatus
    text: str | None = None
    error_code: JobErrorCode | None = None


def ping(text: str = "Hello", *, job_id: UUID | None = None) -> Ping:
    return Ping(job_id=job_id or uuid4(), text=text)


def pong_for(request: Ping, text: str | None = None) -> Pong:
    return Pong(
        job_id=request.job_id,
        status=JobResultStatus.COMPLETED,
        text=text if text is not None else f"echo: {request.text}",
    )


def failed_pong(request: Ping, error_code: JobErrorCode) -> Pong:
    return Pong(job_id=request.job_id, status=JobResultStatus.FAILED, error_code=error_code)


class EchoHandler:
    """Answers every `Ping` with its text echoed; counts calls and signals the first."""

    def __init__(self, *, delay: float = 0, error: BaseException | None = None) -> None:
        self.delay = delay
        self.error = error
        self.calls = 0
        self.started = asyncio.Event()

    async def handle(self, request: Ping) -> Pong:
        self.calls += 1
        self.started.set()
        await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return pong_for(request)

    def failed(self, request: Ping, error_code: JobErrorCode) -> Pong:
        return failed_pong(request, error_code)
