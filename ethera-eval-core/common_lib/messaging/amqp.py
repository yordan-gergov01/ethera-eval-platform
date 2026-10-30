"""Turning an envelope into an AMQP message, identically in both services.

Role: `envelope_message`, the one place that sets the AMQP message properties.
Used by: `backend.messaging.publisher`, `runner.worker`.
Depends on: `common_lib.messaging.envelope`, `common_lib.messaging.jobs`, aio-pika.
Key invariants: messages are persistent JSON; `message_id`, `correlation_id` (the job ID), `type`
  and `timestamp` mirror the envelope as AMQP properties — `backend.messaging.consumers` falls back
  to `correlation_id` to find the job of a dead-lettered request whose body cannot be parsed
  (template_core D-003).
"""

from aio_pika import DeliveryMode, Message

from common_lib.messaging.envelope import Envelope
from common_lib.messaging.jobs import JobPayload


def envelope_message[PayloadT: JobPayload](envelope: Envelope[PayloadT]) -> Message:
    """A persistent JSON message carrying the envelope's IDs and type as AMQP properties."""
    return Message(
        envelope.model_dump_json().encode(),
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        message_id=str(envelope.message_id),
        correlation_id=str(envelope.correlation_id),
        type=envelope.message_type.value,
        timestamp=envelope.occurred_at,
    )
