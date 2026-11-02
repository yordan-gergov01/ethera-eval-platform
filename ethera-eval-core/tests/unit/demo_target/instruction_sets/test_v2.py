"""Golden samples of instruction set v2, pinned to its version, the `/chat` schema and the model.

Role: FR-207 for `demo_target/instruction_sets/v2.md`: the file's SHA-256 is pinned, the file
  alone carries R4's escalation instruction, and full `/chat` bodies are pinned for small-v1 and
  medium-v1 with `keyword`: questions nothing covers escalate with no fact (R4), sourced answers
  stay as under v1 (R5 included), with usage counting the longer instruction set.
Used by: pytest (unit; no services).
Depends on: _samples.py in this folder; `demo_target.behaviour` (`ESCALATION_INSTRUCTION`),
  `demo_target.configuration` (`read_instruction_set`).
Key invariants: a sample is changed only together with the instruction set or the model it
  pins, never to make a behaviour change pass unnoticed.
"""

import pytest

from demo_target.behaviour import ESCALATION_INSTRUCTION
from demo_target.configuration import InstructionSet, read_instruction_set
from tests.unit.demo_target.instruction_sets._samples import (
    ESCALATION,
    SHIPPING_COST,
    WINDOW,
    answer,
    body,
    instruction_set_digest,
)

V2_SHA256 = "712201f229294fb59c2dc667555fdbae3e62b2d8f684348e2e337b3dc23ba46e"
SMALL_V1 = "mock-gen-small-v1"
MEDIUM_V1 = "mock-gen-medium-v1"
INVENTED_SHIPPING = "Return shipping is free on every order."

SAMPLES = [
    (
        SMALL_V1,
        "How do I send them back?",
        body(
            SMALL_V1,
            answer=ESCALATION,
            retrieved=[],
            facts=[],
            decision="escalate",
            usage=(158, 32),
            latency_ms=1169,
        ),
    ),
    (
        SMALL_V1,
        "Is return shipping free?",
        body(
            SMALL_V1,
            answer=f"Here is what I can tell you. {WINDOW} {SHIPPING_COST} {INVENTED_SHIPPING}",
            retrieved=["returns", "shipping"],
            facts=[("returns", WINDOW), ("returns", SHIPPING_COST), (None, INVENTED_SHIPPING)],
            decision="answer_from_docs",
            usage=(219, 64),
            latency_ms=421,
        ),
    ),
    (
        MEDIUM_V1,
        "I bought these sneakers 5 weeks ago, can I return them?",
        body(
            MEDIUM_V1,
            answer=f"Sorry, this item can no longer be returned. {WINDOW}",
            retrieved=["returns"],
            facts=[("returns", WINDOW)],
            decision="deny_return",
            usage=(214, 48),
            latency_ms=2867,
        ),
    ),
    (
        MEDIUM_V1,
        "Can I pay with crypto?",
        body(
            MEDIUM_V1,
            answer=ESCALATION,
            retrieved=[],
            facts=[],
            decision="escalate",
            usage=(158, 32),
            latency_ms=3488,
        ),
    ),
    (
        MEDIUM_V1,
        "Is return shipping free?",
        body(
            MEDIUM_V1,
            answer=f"Here is what I can tell you. {WINDOW} {SHIPPING_COST}",
            retrieved=["returns", "shipping"],
            facts=[("returns", WINDOW), ("returns", SHIPPING_COST)],
            decision="answer_from_docs",
            usage=(219, 64),
            latency_ms=2116,
        ),
    ),
]


def test_instruction_set_v2_is_the_pinned_version() -> None:
    assert instruction_set_digest("v2") == V2_SHA256


def test_instruction_set_v2_alone_carries_the_escalation_instruction() -> None:
    assert ESCALATION_INSTRUCTION in read_instruction_set(InstructionSet.V2)
    assert ESCALATION_INSTRUCTION not in read_instruction_set(InstructionSet.V1)


@pytest.mark.parametrize(("model", "question", "expected"), SAMPLES)
async def test_chat_v2_answers_its_golden_samples(
    model: str, question: str, expected: dict[str, object]
) -> None:
    assert await answer(model, "v2", "keyword", question) == expected
