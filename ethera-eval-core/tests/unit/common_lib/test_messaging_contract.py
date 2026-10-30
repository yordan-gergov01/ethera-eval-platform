"""The message contract: round trips, strict validation, and the queue topology.

Role: pins common_lib.messaging (`envelope`, `jobs`, `topology`, `amqp`): the closed sets of
  message types and error codes, envelope round trips and wire field names, strict validation
  (extra fields, schema version, correlation id, message type, request id, timestamps), and the
  exchange, queue and dead-letter topology, matched against the broker policies and
  permissions in docker/rabbitmq/provision-entrypoint.sh.
Used by: pytest (unit).
Depends on: `Ping`/`Pong`, `ping`, `pong_for`, `failed_pong` from tests/job_payloads.py; the
  provisioning script read as text. No broker.
Key invariants: the machinery is generic over `JobPayload` and exercised with test-local
  payloads until slice 003 brings the real ones (docs/DECISIONS.md D-006); an envelope never
  drops payload fields beyond the base, which is why nothing wraps with `Envelope[JobPayload]`.
"""

import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from common_lib.messaging.amqp import envelope_message
from common_lib.messaging.envelope import Envelope, envelope_type
from common_lib.messaging.jobs import JobErrorCode, JobPayload, MessageType
from common_lib.messaging.topology import (
    DEAD_LETTER_EXCHANGE,
    DELIVERY_LIMIT,
    EXCHANGE,
    JOBS_QUEUE,
    QUEUE_ARGUMENTS,
    RESULTS_QUEUE,
    QueueSpec,
)
from tests.job_payloads import Ping, Pong, failed_pong, ping, pong_for

JOB_ID = UUID("00000000-0000-4000-8000-000000000001")
REQUEST_ID = "req-123"


def requested() -> Ping:
    return ping("Hello", job_id=JOB_ID)


def requested_json(**envelope_overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        Envelope[Ping].wrap(requested(), request_id=REQUEST_ID).model_dump_json()
    )
    return data | envelope_overrides


# --- The closed sets -------------------------------------------------------------------


def test_message_types_are_the_runner_contract() -> None:
    assert {t.value for t in MessageType} == {
        "eval.trial_batch.requested",
        "eval.trial_batch.completed",
    }


def test_error_codes_are_generic_to_any_worker() -> None:
    assert {c.value for c in JobErrorCode} == {
        "HANDLER_TIMEOUT",
        "INVALID_MESSAGE",
        "INTERNAL_ERROR",
    }


# --- Round trips -----------------------------------------------------------------------


def test_job_request_round_trip() -> None:
    message = Envelope[Ping].wrap(requested(), request_id=REQUEST_ID)

    parsed = Envelope[Ping].model_validate_json(message.model_dump_json())

    assert parsed == message
    assert parsed.message_type is MessageType.EVAL_TRIAL_BATCH_REQUESTED
    assert parsed.correlation_id == JOB_ID


def test_job_result_round_trip() -> None:
    message = Envelope[Pong].wrap(pong_for(requested()), request_id=REQUEST_ID)

    parsed = envelope_type(Pong).model_validate_json(message.model_dump_json())

    assert parsed == message
    assert parsed.payload.text == "echo: Hello"


def test_wire_format_field_names() -> None:
    data = requested_json()

    assert set(data) == {
        "schema_version",
        "message_id",
        "message_type",
        "correlation_id",
        "request_id",
        "occurred_at",
        "payload",
    }
    assert set(data["payload"]) == {"job_id", "text"}
    assert data["schema_version"] == 1
    assert data["message_type"] == "eval.trial_batch.requested"


def test_failed_result_round_trip() -> None:
    payload = failed_pong(requested(), JobErrorCode.HANDLER_TIMEOUT)
    message = Envelope[Pong].wrap(payload, request_id=REQUEST_ID)

    parsed = Envelope[Pong].model_validate_json(message.model_dump_json())

    assert parsed.payload.error_code is JobErrorCode.HANDLER_TIMEOUT


def test_an_unparametrised_envelope_keeps_every_payload_field_on_the_wire() -> None:
    # The generic publisher and worker wrap payloads without naming their class.
    message = envelope_message(Envelope.wrap(requested(), request_id=REQUEST_ID))

    parsed = envelope_type(Ping).model_validate_json(message.body)

    assert parsed.payload == requested()
    assert message.type == "eval.trial_batch.requested"


def test_the_base_payload_envelope_would_drop_subclass_fields() -> None:
    # Why the machinery never wraps with Envelope[JobPayload] (see envelope.py).
    envelope = Envelope[JobPayload].wrap(requested(), request_id=REQUEST_ID)

    assert set(json.loads(envelope.model_dump_json())["payload"]) == {"job_id"}


def test_a_message_is_parsed_only_as_its_own_type() -> None:
    body = Envelope[Ping].wrap(requested(), request_id=REQUEST_ID).model_dump_json()

    with pytest.raises(ValidationError):
        envelope_type(Pong).model_validate_json(body)


# --- Strict validation -----------------------------------------------------------------


def test_unknown_envelope_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        Envelope[Ping].model_validate(requested_json(unexpected="x"))


def test_unknown_payload_field_is_rejected() -> None:
    data = requested_json()
    data["payload"]["email"] = "someone@example.com"

    with pytest.raises(ValidationError, match="extra"):
        Envelope[Ping].model_validate(data)


def test_unsupported_schema_version_is_rejected() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        Envelope[Ping].model_validate(requested_json(schema_version=2))


def test_correlation_id_must_match_job_id() -> None:
    with pytest.raises(ValidationError, match="correlation_id"):
        Envelope[Ping].model_validate(requested_json(correlation_id=str(uuid4())))


def test_message_type_must_match_payload() -> None:
    with pytest.raises(ValidationError, match="message_type"):
        Envelope[Ping].model_validate(requested_json(message_type="eval.trial_batch.completed"))


@pytest.mark.parametrize("request_id", ["", "has space", "x" * 129, "line\nbreak"])
def test_invalid_request_id_is_rejected(request_id: str) -> None:
    with pytest.raises(ValidationError, match="request_id"):
        Envelope[Ping].model_validate(requested_json(request_id=request_id))


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="occurred_at"):
        Envelope[Ping].model_validate(requested_json(occurred_at="2026-10-05T08:00:00"))


def test_timestamp_is_normalised_to_utc() -> None:
    sofia = timezone(timedelta(hours=3))
    data = requested_json(occurred_at=datetime(2026, 10, 5, 11, 0, tzinfo=sofia).isoformat())

    message = Envelope[Ping].model_validate(data)

    assert message.occurred_at == datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
    assert message.occurred_at.tzinfo is UTC


def test_unknown_error_code_is_rejected() -> None:
    with pytest.raises(ValidationError, match="error_code"):
        Pong.model_validate(
            {
                "job_id": str(JOB_ID),
                "status": "failed",
                "error_code": "Traceback (most recent call last): ...",
            }
        )


PROVISIONING_SCRIPT = (
    Path(__file__).resolve().parents[3] / "docker" / "rabbitmq" / "provision-entrypoint.sh"
)


# --- Topology --------------------------------------------------------------------------


def test_exchanges_and_queues_are_named_for_the_runner() -> None:
    assert (EXCHANGE, DEAD_LETTER_EXCHANGE) == ("evals", "evals.dlx")
    assert (JOBS_QUEUE.name, JOBS_QUEUE.message_type) == (
        "runner.jobs",
        MessageType.EVAL_TRIAL_BATCH_REQUESTED,
    )
    assert (RESULTS_QUEUE.name, RESULTS_QUEUE.message_type) == (
        "backend.runner.results",
        MessageType.TRIAL_BATCH_COMPLETED,
    )


@pytest.mark.parametrize(
    ("queue", "routing_key", "dead_letter_queue"),
    [
        (JOBS_QUEUE, "trial_batch.requested", "runner.jobs.dlq"),
        (RESULTS_QUEUE, "trial_batch.completed", "backend.runner.results.dlq"),
    ],
)
def test_work_queues_dead_letter_after_the_delivery_limit(
    queue: QueueSpec, routing_key: str, dead_letter_queue: str
) -> None:
    assert queue.routing_key == routing_key
    assert queue.dead_letter_queue == dead_letter_queue
    assert queue.policy() == {
        "dead-letter-exchange": DEAD_LETTER_EXCHANGE,
        "dead-letter-routing-key": routing_key,
        "delivery-limit": DELIVERY_LIMIT,
    }


def test_queues_are_declared_as_quorum_queues_only() -> None:
    # Dead-letter arguments would require read permission to declare the queue.
    assert dict(QUEUE_ARGUMENTS) == {"x-queue-type": "quorum"}


def provisioned_definitions() -> dict[str, Any]:
    """The broker definitions the start-up script renders, with placeholder values."""
    script = PROVISIONING_SCRIPT.read_text(encoding="utf-8")
    heredoc = script.split('cat > "$definitions_file" <<EOF\n', 1)[1].split("\nEOF\n", 1)[0]
    rendered = re.sub(r"\$[A-Z_]+", "placeholder", heredoc)
    definitions: dict[str, Any] = json.loads(rendered)
    return definitions


@pytest.mark.parametrize("queue", [JOBS_QUEUE, RESULTS_QUEUE], ids=lambda q: q.name)
def test_the_broker_policies_match_the_topology(queue: QueueSpec) -> None:
    pattern = "^" + queue.name.replace(".", "[.]") + "$"
    [policy] = [p for p in provisioned_definitions()["policies"] if p["pattern"] == pattern]

    assert policy["apply-to"] == "queues"
    assert policy["definition"] == queue.policy()


def _alternatives(*names: str) -> str:
    return "^(" + "|".join(name.replace(".", "[.]") for name in names) + ")$"


def test_the_broker_permissions_name_the_topology() -> None:
    backend, runner, inspector = provisioned_definitions()["permissions"]
    everything = _alternatives(
        EXCHANGE,
        DEAD_LETTER_EXCHANGE,
        JOBS_QUEUE.name,
        JOBS_QUEUE.dead_letter_queue,
        RESULTS_QUEUE.name,
        RESULTS_QUEUE.dead_letter_queue,
    )

    # Both services declare the whole topology (D-010); each reads only its own queues.
    for service in (backend, runner):
        assert service["configure"] == service["write"] == everything
    assert backend["read"] == _alternatives(
        EXCHANGE, DEAD_LETTER_EXCHANGE, RESULTS_QUEUE.name, JOBS_QUEUE.dead_letter_queue
    )
    assert runner["read"] == _alternatives(EXCHANGE, DEAD_LETTER_EXCHANGE, JOBS_QUEUE.name)
    assert inspector["read"] == _alternatives(
        JOBS_QUEUE.dead_letter_queue, RESULTS_QUEUE.dead_letter_queue
    )


def test_delivery_limit_is_three() -> None:
    assert DELIVERY_LIMIT == 3
