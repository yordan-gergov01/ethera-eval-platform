"""RabbitMQ exchanges, queues and routing, as plain data.

Role: the topology as data:
    exchange "evals" (direct, durable)
      "trial_batch.requested" -> queue "runner.jobs"             (consumed by the runner)
      "trial_batch.completed" -> queue "backend.runner.results"  (consumed by the backend)
    exchange "evals.dlx" (direct, durable)
      "trial_batch.requested" -> queue "runner.jobs.dlq"
      "trial_batch.completed" -> queue "backend.runner.results.dlq"
Used by: `common_lib.messaging.declare`, `backend.messaging` (connection, publisher, consumers),
  `runner.worker`; the broker and messaging tests.
  docker/rabbitmq/provision-entrypoint.sh repeats the names, permissions and policies by hand;
  tests/unit/common_lib/test_messaging_contract.py keeps the two in step.
Depends on: `common_lib.messaging.jobs.MessageType`.
Key invariants: all queues are quorum queues, which count redeliveries, so a message that keeps
  crashing its consumer is dead-lettered after `DELIVERY_LIMIT` redeliveries. Dead-lettering and
  the delivery limit are broker policies, not queue arguments: RabbitMQ requires read permission
  to declare a queue with dead-letter arguments, and the backend declares the job queue without
  being allowed to consume it (template_core D-002, D-010). Names follow D-006.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from common_lib.messaging.jobs import MessageType

EXCHANGE = "evals"
DEAD_LETTER_EXCHANGE = "evals.dlx"
DELIVERY_LIMIT = 3
# Declaration arguments of every queue; everything else comes from policies.
QUEUE_ARGUMENTS: Mapping[str, str] = MappingProxyType({"x-queue-type": "quorum"})

ROUTING_KEYS: Mapping[MessageType, str] = MappingProxyType(
    {
        MessageType.EVAL_TRIAL_BATCH_REQUESTED: "trial_batch.requested",
        MessageType.TRIAL_BATCH_COMPLETED: "trial_batch.completed",
    }
)


@dataclass(frozen=True, slots=True)
class QueueSpec:
    """A work queue bound to `EXCHANGE`, with its dead-letter queue on `DEAD_LETTER_EXCHANGE`."""

    name: str
    message_type: MessageType
    dead_letter_queue: str

    @property
    def routing_key(self) -> str:
        return ROUTING_KEYS[self.message_type]

    def policy(self) -> dict[str, str | int]:
        """The broker policy the provisioning applies to the work queue."""
        return {
            "dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "dead-letter-routing-key": self.routing_key,
            "delivery-limit": DELIVERY_LIMIT,
        }


JOBS_QUEUE = QueueSpec(
    name="runner.jobs",
    message_type=MessageType.EVAL_TRIAL_BATCH_REQUESTED,
    dead_letter_queue="runner.jobs.dlq",
)
RESULTS_QUEUE = QueueSpec(
    name="backend.runner.results",
    message_type=MessageType.TRIAL_BATCH_COMPLETED,
    dead_letter_queue="backend.runner.results.dlq",
)
