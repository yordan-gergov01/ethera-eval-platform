"""Shared vocabulary of the golden-sample tests: the expected `/chat` body and its parts.

Role: builds the full expected `/chat` response body (contract §2.3 schema) of a golden sample
  from its parts, with the model's declared prices, and runs a sample against the demo target.
Used by: tests/unit/demo_target/instruction_sets/test_v1.py and test_v2.py.
Depends on: the §6 helper `demo_target_client` in tests/integration/evaluation_fixtures.py; httpx.
Key invariants: the prices here are typed from contract §3.3, never read from the demo target;
  bodies are compared whole, so a renamed, added or dropped field fails the samples.
"""

import hashlib
from pathlib import Path

import demo_target
from tests.integration.evaluation_fixtures import demo_target_client

PRICES = {
    "mock-gen-small-v1": ("0.20", "0.80"),
    "mock-gen-small-v2": ("0.20", "0.80"),
    "mock-gen-medium-v1": ("0.50", "2.00"),
}
WINDOW = "Returns are accepted within 30 days of delivery."
SHIPPING_COST = "Return shipping costs 4.90, deducted from the refund."
DEFECT = "Items damaged on arrival or defective within 90 days of delivery are refunded in full."
STEPS = "Start a return from your order page, pack the item and hand the parcel to the courier."
ESCALATION = "I cannot answer that from our help center, so let me connect you with a colleague."

Fact = tuple[str | None, str]


def body(
    model: str,
    *,
    answer: str,
    retrieved: list[str],
    facts: list[Fact],
    decision: str,
    usage: tuple[int, int],
    latency_ms: int,
) -> dict[str, object]:
    """The full expected `/chat` body of one golden sample."""
    input_price, output_price = PRICES[model]
    return {
        "answer": answer,
        "retrieved_doc_ids": retrieved,
        "facts_used": [{"source": source, "statement": text} for source, text in facts],
        "decision": decision,
        "usage": {"input_tokens": usage[0], "output_tokens": usage[1]},
        "pricing": {
            "input_per_million": input_price,
            "output_per_million": output_price,
            "currency": "USD",
        },
        "latency_ms": latency_ms,
    }


async def answer(model: str, instruction_set: str, retrieval: str, question: str) -> object:
    """The demo target's `/chat` body for `question` in one configuration (asserting a 200)."""
    async with demo_target_client(model, instruction_set, retrieval) as target:
        response = await target.post("/chat", json={"question": question})
    assert response.status_code == 200, response.text
    return response.json()


def instruction_set_digest(version: str) -> str:
    """SHA-256 of the instruction set's `.md` file as shipped in the package."""
    path = Path(demo_target.__file__).parent / "instruction_sets" / f"{version}.md"
    return hashlib.sha256(path.read_bytes()).hexdigest()
