"""Versioned envelope wrapped around every message payload.

Role: `Envelope` (schema version, message ID, type, correlation ID, request ID, UTC timestamp,
  payload) and `envelope_type`, which parametrises it with a payload type chosen at runtime.
Used by: `backend.messaging.publisher`, `backend.messaging.consumers`, `common_lib.messaging.amqp`,
  `runner.worker`; the messaging contract and job tests.
Depends on: `common_lib.messaging.jobs`, `common_lib.request_id.REQUEST_ID_PATTERN`, pydantic.
Key invariants: validated strictly on both sides (`extra="forbid"`, frozen) (template_core D-003).
  `correlation_id` is the job ID and `message_type` must match the payload, both checked.
  `message_id` lets consumers recognise redeliveries. Build outgoing envelopes with the
  unparametrised `Envelope.wrap(...)` or the payload's own class: `Envelope[JobPayload]` would
  serialise only the base fields, silently dropping the rest. The `type: ignore` in
  `envelope_type` is deliberate (mypy cannot express it).
"""

from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from common_lib.messaging.jobs import JobPayload, MessageType
from common_lib.request_id import REQUEST_ID_PATTERN

SCHEMA_VERSION: Literal[1] = 1


class Envelope[PayloadT: JobPayload](BaseModel):
    """A message on the broker: metadata for routing, tracing and deduplication.

    `correlation_id` is the job ID, so a result is matched to its request without
    any other state. `message_id` is unique per message and lets consumers
    recognise redeliveries. Parse a received message with the concrete payload type,
    for example `envelope_type(SomePayload).model_validate_json(body)`.

    Build an outgoing envelope with the unparametrised `Envelope.wrap(payload, ...)` or
    with the payload's own class. `Envelope[JobPayload]` would validate a subclass
    instance but serialise only the base fields, silently dropping the rest.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = SCHEMA_VERSION
    message_id: UUID = Field(default_factory=uuid4)
    message_type: MessageType
    correlation_id: UUID
    request_id: str = Field(pattern=REQUEST_ID_PATTERN)
    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: PayloadT

    @classmethod
    def wrap(cls, payload: PayloadT, *, request_id: str) -> Self:
        """Build the envelope for a payload, deriving its type and correlation ID."""
        return cls(
            message_type=payload.MESSAGE_TYPE,
            correlation_id=payload.job_id,
            request_id=request_id,
            payload=payload,
        )

    @field_validator("occurred_at")
    @classmethod
    def _normalise_to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _metadata_matches_payload(self) -> Self:
        if self.message_type is not self.payload.MESSAGE_TYPE:
            raise ValueError("message_type does not match the payload")
        if self.correlation_id != self.payload.job_id:
            raise ValueError("correlation_id must equal payload.job_id")
        return self


def envelope_type[PayloadT: JobPayload](payload_type: type[PayloadT]) -> type[Envelope[PayloadT]]:
    """The envelope class for one payload type, chosen at runtime, for parsing messages.

    Generic machinery (publisher, consumers, worker) receives its payload types as
    arguments, so the envelope must be parametrised with a runtime value.
    """
    # mypy cannot express parametrising a generic class with a variable; pydantic builds
    # (and caches) the concrete class at runtime, which is exactly the type returned.
    return Envelope[payload_type]  # type: ignore[valid-type]
