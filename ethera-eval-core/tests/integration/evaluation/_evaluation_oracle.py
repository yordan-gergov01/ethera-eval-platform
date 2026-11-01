"""Evaluation oracle vocabulary: paths, the contract's tables, and the Dataset/chat helpers.

Role: the HTTP-level helpers of the sealed oracle for specs/002-demo-target-and-dataset/contract.md
  — the two Dataset paths (§2.1, §2.2), the §3.5 table of seeded Goldens, the value sets, the
  §3.3 model table and §3.4 configurations, the C-212 pass rule, and shape checks for `/chat`.
Used by: every test module in tests/integration/evaluation/.
Depends on: tests/integration/conftest.py (`assert_problem`, `bearer`); the slice 001 oracle
  vocabulary in tests/integration/registry/_registry_oracle.py; _contract_fixtures.py.
Key invariants: every table here is copied from the contract (the §3.5 `input` and `rule` texts
  were extracted from contract.md by script and compared back to it, em and en dashes
  included), never from the implementation; nothing from `backend.*`, `evals.*`, `runner.*`,
  `demo_target.*` or `common_lib.*` is imported.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from httpx import AsyncClient, Response

from tests.integration.conftest import assert_problem, bearer
from tests.integration.registry._registry_oracle import ACME, SUPPORT_BOT, product_path

DECISIONS = frozenset(
    {
        "approve_return",
        "deny_return",
        "explain_return",
        "approve_refund",
        "deny_refund",
        "report_status",
        "answer_from_docs",
        "escalate",
    }
)
FAILURE_TYPES = (
    "date_math",
    "refund_rules",
    "invented_facts",
    "out_of_docs",
    "retrieval_miss",
    "order_status_tool",
)
OWNERS = (None, "engineering", "support_content")
DOCUMENTS = frozenset({"returns", "refunds", "shipping"})
ORDER_TOOL = "tool:orders"
SOURCES = DOCUMENTS | {ORDER_TOOL}
GOLDEN_KEYS = frozenset(
    {
        "position",
        "input",
        "expected_decision",
        "rule",
        "failure_type",
        "context",
        "expected_numbers",
        "owner",
        "unfixable_by_code",
    }
)
CHAT_KEYS = frozenset(
    {"answer", "retrieved_doc_ids", "facts_used", "decision", "usage", "pricing", "latency_ms"}
)
DECIMAL_STRING = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")

_RETURNS_30 = "Returns within 30 days of delivery — doc returns"
_STEPS = "Return steps — doc returns"
_DEFECT_90 = "Defects within 90 days of delivery: full refund — doc refunds"

# §3.5: (position, input, expected_decision, rule, failure_type, expected_numbers).
SEEDED_GOLDENS: tuple[tuple[int, str, str, str, str, tuple[str, ...]], ...] = (
    (1, "I bought these sneakers 5 weeks ago, can I return them?", "deny_return", _RETURNS_30, "date_math", ("30",)),  # noqa: E501
    (2, "My boots were delivered 40 days ago. Can I still return them?", "deny_return", _RETURNS_30, "date_math", ("30",)),  # noqa: E501
    (3, "I received my order 6 weeks ago, can I return it?", "deny_return", _RETURNS_30, "date_math", ("30",)),  # noqa: E501
    (4, "Bought them 10 days ago, can I return them?", "approve_return", _RETURNS_30, "date_math", ("30",)),  # noqa: E501
    (5, "I got these 3 weeks ago, can I send them back?", "approve_return", _RETURNS_30, "date_math", ("30",)),  # noqa: E501
    (6, "How do I send them back?", "explain_return", _STEPS, "retrieval_miss", ()),
    (7, "What's the process to ship my shoes back to you?", "explain_return", _STEPS, "retrieval_miss", ()),  # noqa: E501
    (8, "Can I pay with crypto?", "escalate", "No document covers payment methods; offer a human", "out_of_docs", ()),  # noqa: E501
    (9, "Do you offer student discounts?", "escalate", "No document covers discounts; offer a human", "out_of_docs", ()),  # noqa: E501
    (10, "Do you sell gift cards?", "answer_from_docs", "Gift-card policy — document to be written by the support content team", "out_of_docs", ()),  # noqa: E501
    (11, "Where is order 1042?", "report_status", "Status from the order tool", "order_status_tool", ()),  # noqa: E501
    (12, "What's the status of order 1077?", "report_status", "Status from the order tool", "order_status_tool", ()),  # noqa: E501
    (13, "Where is order 9999?", "report_status", "Status from the order tool; unknown orders are reported as unknown", "order_status_tool", ()),  # noqa: E501
    (14, "The sole came off after a week. Can I get a refund?", "approve_refund", _DEFECT_90, "refund_rules", ("90",)),  # noqa: E501
    (15, "I noticed a defect after 15 weeks. Can I get a refund?", "deny_refund", _DEFECT_90, "refund_rules", ("90",)),  # noqa: E501
    (16, "My shoes arrived damaged yesterday, do I get my money back?", "approve_refund", "Damaged on arrival: full refund — doc refunds", "refund_rules", ()),  # noqa: E501
    (17, "I wore the shoes outside and changed my mind. Can I get a refund?", "deny_refund", "Worn items are refunded only when defective — doc refunds", "refund_rules", ()),  # noqa: E501
    (18, "Is return shipping free?", "answer_from_docs", "Return shipping costs 4.90, deducted from the refund — doc returns", "invented_facts", ("4.90",)),  # noqa: E501
    (19, "How long does a refund take?", "answer_from_docs", "Refunds arrive in 5–7 business days — doc refunds", "invented_facts", ("5", "7")),  # noqa: E501, RUF001
)  # fmt: skip
SEEDED_QUESTIONS = tuple(row[1] for row in SEEDED_GOLDENS)
SEEDED_COUNTS = {
    "date_math": 5,
    "refund_rules": 4,
    "invented_facts": 2,
    "out_of_docs": 3,
    "retrieval_miss": 2,
    "order_status_tool": 3,
}


@dataclass(frozen=True)
class Model:
    input_per_million: Decimal
    output_per_million: Decimal
    latency_min: int
    latency_max: int


SMALL_V1 = "mock-gen-small-v1"
SMALL_V2 = "mock-gen-small-v2"
MEDIUM_V1 = "mock-gen-medium-v1"
MODELS = {
    SMALL_V1: Model(Decimal("0.20"), Decimal("0.80"), 400, 1200),
    SMALL_V2: Model(Decimal("0.20"), Decimal("0.80"), 400, 1200),
    MEDIUM_V1: Model(Decimal("0.50"), Decimal("2.00"), 1500, 3500),
}

Config = tuple[str, str, str]  # (model, instruction set, retrieval mode)
CONFIGS: dict[str, Config] = {
    "B": (SMALL_V1, "v1", "keyword"),
    "PR": (SMALL_V1, "v2", "keyword"),
    "Ret": (SMALL_V1, "v1", "semantic"),
    "Rel": (SMALL_V2, "v1", "keyword"),
    "Exp": (MEDIUM_V1, "v1", "keyword"),
}
BASELINE = CONFIGS["B"]


def dataset_path(client_id: str = ACME, project_id: str = SUPPORT_BOT) -> str:
    return f"{product_path(client_id, project_id)}/dataset"


def version_path(segment: object, client_id: str = ACME, project_id: str = SUPPORT_BOT) -> str:
    return f"{dataset_path(client_id, project_id)}/versions/{segment}"


async def read_summary(
    api: AsyncClient, token: str, client_id: str = ACME, project_id: str = SUPPORT_BOT
) -> dict[str, Any]:
    """§2.1, asserting the 200 and the identity of the answer."""
    response = await api.get(dataset_path(client_id, project_id), headers=bearer(token))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert (body["client_id"], body["project_id"]) == (client_id, project_id), body
    return body


async def read_version(
    api: AsyncClient,
    token: str,
    number: int,
    client_id: str = ACME,
    project_id: str = SUPPORT_BOT,
) -> dict[str, Any]:
    """§2.2, asserting the 200, the identity of the answer and the shape of every Golden."""
    response = await api.get(version_path(number, client_id, project_id), headers=bearer(token))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert (body["client_id"], body["project_id"], body["number"]) == (
        client_id,
        project_id,
        number,
    ), body
    assert_golden_shapes(body["goldens"])
    return body


def assert_golden_shapes(goldens: list[dict[str, Any]]) -> None:
    """§2.2 Golden: exact keys, positions 1..n, value sets, decimal-string numbers."""
    assert [golden["position"] for golden in goldens] == list(range(1, len(goldens) + 1))
    for golden in goldens:
        assert set(golden) == GOLDEN_KEYS, golden
        assert golden["expected_decision"] in DECISIONS, golden
        assert golden["failure_type"] in FAILURE_TYPES, golden
        assert golden["owner"] in OWNERS, golden
        assert isinstance(golden["unfixable_by_code"], bool), golden
        assert golden["context"] is None or isinstance(golden["context"], str), golden
        assert isinstance(golden["expected_numbers"], list), golden
        for number in golden["expected_numbers"]:
            assert isinstance(number, str), golden
            assert DECIMAL_STRING.match(number), golden


def stable_problem(response: Response, status: int, code: str) -> dict[str, Any]:
    """A problem body of the given status and code, without its per-request fields."""
    body = assert_problem(response, status, code)
    for key in ("status", "code", "detail", "instance", "request_id"):
        assert key in body, body
    return {k: v for k, v in body.items() if k not in ("instance", "request_id")}


def golden(
    input_text: str,
    failure_type: str = "date_math",
    *,
    expected_decision: str = "deny_return",
    rule: str = "An arranged rule",
    context: str | None = None,
    expected_numbers: tuple[str, ...] = (),
    owner: str | None = None,
    unfixable_by_code: bool = False,
) -> dict[str, object]:
    """One Golden for `arrange_dataset_version`: the §2.2 fields except `position`."""
    return {
        "input": input_text,
        "expected_decision": expected_decision,
        "rule": rule,
        "failure_type": failure_type,
        "context": context,
        "expected_numbers": list(expected_numbers),
        "owner": owner,
        "unfixable_by_code": unfixable_by_code,
    }


async def chat(target: AsyncClient, question: str) -> Response:
    return await target.post("/chat", json={"question": question})


def assert_chat_shape(body: dict[str, Any], model: str) -> None:
    """Every §2.3 clause that holds for any 200 of `/chat` under `model`."""
    assert set(body) == CHAT_KEYS, body
    assert isinstance(body["answer"], str), body
    assert body["answer"], body
    retrieved = body["retrieved_doc_ids"]
    assert isinstance(retrieved, list), body
    assert set(retrieved) <= SOURCES, body
    assert retrieved == sorted(retrieved), body
    assert len(retrieved) == len(set(retrieved)), body
    assert isinstance(body["facts_used"], list), body
    for fact in body["facts_used"]:
        assert set(fact) == {"source", "statement"}, fact
        assert isinstance(fact["statement"], str), fact
        assert fact["statement"], fact
        # C-208: a non-null source is "a retrieved document ID or tool:orders" — retrieved.
        assert fact["source"] is None or fact["source"] in retrieved, (fact, retrieved)
    assert body["decision"] in DECISIONS, body
    usage = body["usage"]
    assert set(usage) == {"input_tokens", "output_tokens"}, usage
    for count in usage.values():
        assert type(count) is int, usage
        assert count > 0, usage
    assert_pricing(body["pricing"], model)
    latency = body["latency_ms"]
    assert type(latency) is int, body
    assert MODELS[model].latency_min <= latency <= MODELS[model].latency_max, (model, latency)


def assert_pricing(pricing: dict[str, Any], model: str) -> None:
    assert set(pricing) == {"input_per_million", "output_per_million", "currency"}, pricing
    assert pricing["currency"] == "USD", pricing
    for key in ("input_per_million", "output_per_million"):
        assert isinstance(pricing[key], str), pricing
        assert DECIMAL_STRING.match(pricing[key]), pricing
    assert Decimal(pricing["input_per_million"]) == MODELS[model].input_per_million, pricing
    assert Decimal(pricing["output_per_million"]) == MODELS[model].output_per_million, pricing


def cost(body: dict[str, Any]) -> Decimal:
    """The call's cost in USD from its own usage and declared prices (C-209, C-210)."""
    usage, pricing = body["usage"], body["pricing"]
    return (
        Decimal(usage["input_tokens"]) * Decimal(pricing["input_per_million"])
        + Decimal(usage["output_tokens"]) * Decimal(pricing["output_per_million"])
    ) / Decimal(1_000_000)


def passes(body: dict[str, Any], expected_decision: str) -> bool:
    """C-212: decision equal, and every asserted fact sourced from a retrieved source."""
    retrieved = set(body["retrieved_doc_ids"])
    sourced = all(
        fact["source"] is not None and fact["source"] in retrieved for fact in body["facts_used"]
    )
    return bool(body["decision"] == expected_decision and sourced)
