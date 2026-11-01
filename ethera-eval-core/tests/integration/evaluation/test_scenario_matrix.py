"""Sealed oracle: the scenario matrix — every seeded Golden in every demo configuration.

Role: pins §3.4 of specs/002-demo-target-and-dataset/contract.md (spec FR-210, SC-204; PP-206,
  PP-211): every ✓/✗ cell, judged by the C-212 pass rule on real `/chat` responses to the
  seeded Goldens as read through §2.2; the brief's scenario readings (fixed, zero regressions)
  derived from the observed outcomes; and the observable behaviour R1, R3 to R6 the matrix rests on.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/evaluation/conftest.py; _evaluation_oracle.py; the §6
  helper `demo_target_client` through _contract_fixtures.py.
Key invariants: the questions come from the API (never from the typed §3.5 copy), so a seed and
  a behaviour that drift apart fail; MATRIX below is the contract's table typed verbatim and is
  the oracle; each column is compared whole, so every wrong cell shows at once; R3/R4 are checked
  as conditionals over every observed response, anchored by R1 (Goldens 5 to 7 retrieve nothing
  under `keyword`) so the condition is known to occur.
"""

from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.evaluation._contract_fixtures import demo_target_client
from tests.integration.evaluation._evaluation_oracle import (
    CONFIGS,
    DOCUMENTS,
    MEDIUM_V1,
    ORDER_TOOL,
    assert_chat_shape,
    chat,
    passes,
    read_version,
)
from tests.integration.registry._registry_oracle import admin_token

COLUMNS = ("B", "PR", "Ret", "Rel", "Exp")
# §3.4 verbatim: Golden position -> (B, PR, Ret, Rel, Exp); True is ✓, False is ✗.
MATRIX: dict[int, tuple[bool, bool, bool, bool, bool]] = {
    1: (False, False, False, True, True),
    2: (True, True, True, True, True),
    3: (False, False, False, True, True),
    4: (True, True, True, True, True),
    5: (False, False, True, False, False),
    6: (False, False, True, False, False),
    7: (False, False, True, False, False),
    8: (False, True, False, False, True),
    9: (False, True, False, False, True),
    10: (False, False, False, False, False),
    11: (True, True, True, True, True),
    12: (True, True, True, True, True),
    13: (True, True, True, True, True),
    14: (True, True, True, True, True),
    15: (False, False, False, True, True),
    16: (True, True, True, True, True),
    17: (True, True, True, True, True),
    18: (False, False, False, False, True),
    19: (True, True, True, True, True),
}

Responses = dict[int, dict[str, Any]]  # Golden position -> /chat body


async def seeded_goldens(api: AsyncClient) -> list[dict[str, Any]]:
    """Version 1 of acme / support-bot, read through §2.2."""
    goldens: list[dict[str, Any]] = (await read_version(api, await admin_token(api), 1))["goldens"]
    assert [golden["position"] for golden in goldens] == list(MATRIX)
    return goldens


async def run_config(name: str, goldens: list[dict[str, Any]]) -> Responses:
    model, instruction_set, retrieval = CONFIGS[name]
    responses: Responses = {}
    async with demo_target_client(model, instruction_set, retrieval) as target:
        for golden in goldens:
            response = await chat(target, golden["input"])
            assert response.status_code == 200, (name, golden["position"], response.text)
            body: dict[str, Any] = response.json()
            assert_chat_shape(body, model)
            responses[golden["position"]] = body
    return responses


async def run_all(api: AsyncClient) -> tuple[list[dict[str, Any]], dict[str, Responses]]:
    goldens = await seeded_goldens(api)
    return goldens, {name: await run_config(name, goldens) for name in COLUMNS}


def outcomes(goldens: list[dict[str, Any]], responses: Responses) -> dict[int, bool]:
    return {
        g["position"]: passes(responses[g["position"]], g["expected_decision"]) for g in goldens
    }


def documents_of(body: dict[str, Any]) -> list[str]:
    return [source for source in body["retrieved_doc_ids"] if source in DOCUMENTS]


@pytest.mark.parametrize("column", COLUMNS)
async def test_every_seeded_golden_has_its_contract_outcome(api: AsyncClient, column: str) -> None:
    goldens = await seeded_goldens(api)
    responses = await run_config(column, goldens)
    index = COLUMNS.index(column)
    expected = {position: row[index] for position, row in MATRIX.items()}
    assert outcomes(goldens, responses) == expected


async def test_each_scenario_fixes_its_goldens_without_regressions(api: AsyncClient) -> None:
    goldens, everything = await run_all(api)
    seen = {name: outcomes(goldens, responses) for name, responses in everything.items()}
    baseline = seen["B"]

    def fixed(name: str) -> set[int]:
        return {p for p, ok in seen[name].items() if ok and not baseline[p]}

    def regressed(name: str) -> set[int]:
        return {p for p, ok in seen[name].items() if baseline[p] and not ok}

    assert (fixed("PR"), regressed("PR")) == ({8, 9}, set())
    assert (fixed("Ret"), regressed("Ret")) == ({5, 6, 7}, set())
    assert (fixed("Rel"), regressed("Rel")) == ({1, 3, 15}, set())
    assert (fixed("Exp"), regressed("Exp")) == ({1, 3, 8, 9, 15, 18}, set())
    assert not any(seen[name][10] for name in COLUMNS)


async def test_retrieval_mode_decides_whether_return_steps_are_found(api: AsyncClient) -> None:
    goldens, everything = await run_all(api)
    for position in (5, 6, 7):  # R1
        assert "returns" in documents_of(everything["Ret"][position]), position
        for name in ("B", "PR", "Rel", "Exp"):
            assert documents_of(everything[name][position]) == [], (name, position)
    assert len(goldens) == 19


async def test_without_any_source_small_v1_invents_and_v2_or_medium_escalate(
    api: AsyncClient,
) -> None:
    _, everything = await run_all(api)
    unsourced = 0
    for name, responses in everything.items():
        model, instruction_set, _ = CONFIGS[name]
        for position, body in responses.items():
            if body["retrieved_doc_ids"]:
                continue
            unsourced += 1
            if instruction_set == "v2" or model == MEDIUM_V1:  # R3 (medium), R4
                assert body["decision"] == "escalate", (name, position)
            else:  # R3 (small models under v1)
                assert None in [fact["source"] for fact in body["facts_used"]], (name, position)
    assert unsourced >= 12  # anchor: R1 makes Goldens 5 to 7 sourceless in the four keyword columns


async def test_instruction_set_v2_changes_only_sourceless_answers(api: AsyncClient) -> None:
    _, everything = await run_all(api)
    compared: set[int] = set()
    for position, baseline in everything["B"].items():  # R4: same model and retrieval as PR
        candidate = everything["PR"][position]
        if not baseline["retrieved_doc_ids"]:
            continue
        compared.add(position)
        for key in ("retrieved_doc_ids", "decision", "facts_used"):
            assert candidate[key] == baseline[key], (position, key)
    assert {11, 12, 13} <= compared  # anchor: R6 gives the order questions a source


async def test_small_models_invent_the_return_shipping_fact(api: AsyncClient) -> None:
    _, everything = await run_all(api)
    for name in ("B", "PR", "Ret", "Rel"):  # R5
        sources = [fact["source"] for fact in everything[name][18]["facts_used"]]
        assert None in sources, (name, sources)
    assert None not in [fact["source"] for fact in everything["Exp"][18]["facts_used"]]


async def test_order_questions_call_the_order_tool_in_every_configuration(
    api: AsyncClient,
) -> None:
    _, everything = await run_all(api)
    for name in COLUMNS:  # R6
        for position in (11, 12, 13):
            assert ORDER_TOOL in everything[name][position]["retrieved_doc_ids"], (name, position)
