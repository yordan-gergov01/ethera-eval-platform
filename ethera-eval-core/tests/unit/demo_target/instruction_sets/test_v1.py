"""Golden samples of instruction set v1, pinned to its version, the `/chat` schema and the model.

Role: FR-207 for `demo_target/instruction_sets/v1.md`: the file's SHA-256 is pinned (a changed
  instruction set must come with new samples), and full `/chat` bodies — answer texts, sources,
  decision, usage, prices and latency — are pinned per model and retrieval mode: small-v1 with
  `keyword` (the Baseline's date-math bug, R3 inventions, R5, the order tool) and small-v2 with
  `semantic` (correct week arithmetic, the synonym table).
Used by: pytest (unit; no services).
Depends on: _samples.py in this folder.
Key invariants: a sample is changed only together with the instruction set or the model it
  pins, never to make a behaviour change pass unnoticed.
"""

import pytest

from tests.unit.demo_target.instruction_sets._samples import (
    DEFECT,
    SHIPPING_COST,
    STEPS,
    WINDOW,
    answer,
    body,
    instruction_set_digest,
)

V1_SHA256 = "2de329b9b28da0c15f78594596c56d2555b1643746d3daf915c524875b5319fb"
SMALL_V1 = "mock-gen-small-v1"
SMALL_V2 = "mock-gen-small-v2"
INVENTED_SHIPPING = "Return shipping is free on every order."

SAMPLES = [
    (
        SMALL_V1,
        "keyword",
        "I bought these sneakers 5 weeks ago, can I return them?",
        body(
            SMALL_V1,
            answer=f"Yes, you can still return it. {WINDOW}",
            retrieved=["returns"],
            facts=[("returns", WINDOW)],
            decision="approve_return",
            usage=(194, 48),
            latency_ms=1193,
        ),
    ),
    (
        SMALL_V1,
        "keyword",
        "How do I send them back?",
        body(
            SMALL_V1,
            answer="Here is how to return it. Returns are accepted within 14 days.",
            retrieved=[],
            facts=[(None, "Returns are accepted within 14 days.")],
            decision="explain_return",
            usage=(138, 32),
            latency_ms=1169,
        ),
    ),
    (
        SMALL_V1,
        "keyword",
        "Can I pay with crypto?",
        body(
            SMALL_V1,
            answer="Here is what I can tell you. We accept every payment method, crypto included.",
            retrieved=[],
            facts=[(None, "We accept every payment method, crypto included.")],
            decision="answer_from_docs",
            usage=(138, 32),
            latency_ms=572,
        ),
    ),
    (
        SMALL_V1,
        "keyword",
        "Where is order 9999?",
        body(
            SMALL_V1,
            answer="Here is what our order system says. Order 9999 is unknown.",
            retrieved=["tool:orders"],
            facts=[("tool:orders", "Order 9999 is unknown.")],
            decision="report_status",
            usage=(149, 48),
            latency_ms=740,
        ),
    ),
    (
        SMALL_V1,
        "keyword",
        "Is return shipping free?",
        body(
            SMALL_V1,
            answer=f"Here is what I can tell you. {WINDOW} {SHIPPING_COST} {INVENTED_SHIPPING}",
            retrieved=["returns", "shipping"],
            facts=[("returns", WINDOW), ("returns", SHIPPING_COST), (None, INVENTED_SHIPPING)],
            decision="answer_from_docs",
            usage=(199, 64),
            latency_ms=421,
        ),
    ),
    (
        SMALL_V1,
        "keyword",
        "I noticed a defect after 15 weeks. Can I get a refund?",
        body(
            SMALL_V1,
            answer=f"Yes, you get a full refund. {DEFECT}",
            retrieved=["refunds"],
            facts=[("refunds", DEFECT)],
            decision="approve_refund",
            usage=(188, 48),
            latency_ms=672,
        ),
    ),
    (
        SMALL_V2,
        "semantic",
        "I bought these sneakers 5 weeks ago, can I return them?",
        body(
            SMALL_V2,
            answer=f"Sorry, this item can no longer be returned. {WINDOW}",
            retrieved=["returns"],
            facts=[("returns", WINDOW)],
            decision="deny_return",
            usage=(194, 48),
            latency_ms=575,
        ),
    ),
    (
        SMALL_V2,
        "semantic",
        "How do I send them back?",
        body(
            SMALL_V2,
            answer=f"Here is how to return it. {STEPS}",
            retrieved=["returns"],
            facts=[("returns", STEPS)],
            decision="explain_return",
            usage=(186, 48),
            latency_ms=949,
        ),
    ),
    (
        SMALL_V2,
        "semantic",
        "I noticed a defect after 15 weeks. Can I get a refund?",
        body(
            SMALL_V2,
            answer=f"Sorry, this item cannot be refunded. {DEFECT}",
            retrieved=["refunds"],
            facts=[("refunds", DEFECT)],
            decision="deny_refund",
            usage=(188, 48),
            latency_ms=697,
        ),
    ),
]


def test_instruction_set_v1_is_the_pinned_version() -> None:
    assert instruction_set_digest("v1") == V1_SHA256


@pytest.mark.parametrize(("model", "retrieval", "question", "expected"), SAMPLES)
async def test_chat_v1_answers_its_golden_samples(
    model: str, retrieval: str, question: str, expected: dict[str, object]
) -> None:
    assert await answer(model, "v1", retrieval, question) == expected
