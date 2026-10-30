"""The base of every job payload, the message types and the closed set of failure codes.

Role: `MessageType` (the runner's two messages: `EvalTrialBatchRequested`, backend to runner, and
  `TrialBatchCompleted`, runner to backend), `JobErrorCode`, `JobResultStatus`, and the
  `JobPayload` base class.
Used by: `backend.messaging` (publisher, consumers), `common_lib.messaging` (amqp, envelope,
  topology), `runner.worker`; tests/job_payloads.py defines the test-local payloads.
Depends on: pydantic.
Key invariants: the concrete payload classes and fields are added with the feature that sends
  them (slice 003); until then the machinery is generic over `JobPayload` and tested with
  test-local payloads (D-006). Failures cross the boundary only as a closed set of codes
  (template_core D-003). Every payload sets `MESSAGE_TYPE` and is strict (`extra="forbid"`,
  frozen).
"""

from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MessageType(StrEnum):
    """The `type` of every message on the broker."""

    EVAL_TRIAL_BATCH_REQUESTED = "eval.trial_batch.requested"
    TRIAL_BATCH_COMPLETED = "eval.trial_batch.completed"


class JobErrorCode(StrEnum):
    """Why a job failed, as any worker can report it. Only codes cross the boundary."""

    HANDLER_TIMEOUT = "HANDLER_TIMEOUT"
    INVALID_MESSAGE = "INVALID_MESSAGE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class JobResultStatus(StrEnum):
    """Terminal outcome reported by the runner."""

    COMPLETED = "completed"
    FAILED = "failed"


class JobPayload(BaseModel):
    """Base of every job payload: identifies the job the message belongs to.

    Each concrete payload sets `MESSAGE_TYPE`, which the envelope carries and checks.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    MESSAGE_TYPE: ClassVar[MessageType]

    job_id: UUID
