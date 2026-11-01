"""Sealed oracle: the demo target's `POST /chat` — shape, refusals, configuration, determinism.

Role: pins §2.3, §3.3 and §4 of specs/002-demo-target-and-dataset/contract.md: the response
  shape on every §3.5 question in every §3.4 configuration (C-207..C-210), the 1 to 2,000 character
  boundary admitted at its own edge and every malformed body refused with 422 and no answer
  (C-206), unknown configuration values refused on entry (C-211), byte-identical bodies across
  calls, concurrency and restarts, usage independent of the model with the medium model costing
  exactly 2.5x (C-209), and `latency_ms` simulated inside its model's range, never waited.
Used by: pytest (integration; the session probe needs the test database).
Depends on: _evaluation_oracle.py; the §6 helper `demo_target_client` through
  _contract_fixtures.py.
Key invariants: questions here are the typed §3.5 inputs (the matrix test reads them through the
  API instead); every refusal is anchored by a 200 from the same entered target; the factory is
  resolved outside `pytest.raises`, so an absent helper fails rather than counting as a refusal.
"""

import asyncio
import time
from decimal import Decimal
from typing import Any

import pytest

from tests.integration.evaluation._contract_fixtures import (
    demo_target_client,
    demo_target_factory,
)
from tests.integration.evaluation._evaluation_oracle import (
    BASELINE,
    CONFIGS,
    MEDIUM_V1,
    MODELS,
    SEEDED_QUESTIONS,
    SMALL_V1,
    SMALL_V2,
    assert_chat_shape,
    chat,
    cost,
)

ANCHOR_QUESTION = SEEDED_QUESTIONS[1]  # Golden 2, which passes in every configuration


def assert_refused(status: int, content: bytes, label: str) -> None:
    """§4: a 422 that carries no answer and no latency."""
    assert status == 422, (label, content)
    assert b'"answer"' not in content, (label, content)
    assert b'"latency_ms"' not in content, (label, content)


@pytest.mark.parametrize("name", list(CONFIGS))
async def test_every_answer_has_the_contract_shape_and_its_models_prices(name: str) -> None:
    model, instruction_set, retrieval = CONFIGS[name]
    async with demo_target_client(model, instruction_set, retrieval) as target:
        for question in SEEDED_QUESTIONS:
            response = await target.post("/chat", json={"question": question})
            assert response.status_code == 200, (question, response.text)
            assert response.headers["content-type"].startswith("application/json")
            assert_chat_shape(response.json(), model)


@pytest.mark.parametrize("name", list(CONFIGS))
async def test_same_question_gives_byte_identical_bodies_across_calls_and_restarts(
    name: str,
) -> None:
    model, instruction_set, retrieval = CONFIGS[name]
    first: dict[str, bytes] = {}
    async with demo_target_client(model, instruction_set, retrieval) as target:
        for question in SEEDED_QUESTIONS:
            once = await chat(target, question)
            twice = await chat(target, question)
            assert once.status_code == twice.status_code == 200, once.text
            assert once.content == twice.content, question
            first[question] = once.content
    async with demo_target_client(model, instruction_set, retrieval) as restarted:
        for question in reversed(SEEDED_QUESTIONS):
            again = await chat(restarted, question)
            assert again.status_code == 200, again.text
            assert again.content == first[question], question


async def test_concurrent_calls_answer_as_sequential_ones() -> None:
    async with demo_target_client(*BASELINE) as target:
        sequential = [(await chat(target, q)).content for q in SEEDED_QUESTIONS]
        concurrent = await asyncio.gather(*(chat(target, q) for q in SEEDED_QUESTIONS * 2))
    assert all(response.status_code == 200 for response in concurrent)
    assert [response.content for response in concurrent] == sequential * 2


async def test_usage_does_not_depend_on_the_model_and_medium_costs_two_and_a_half_times() -> None:
    bodies: dict[str, list[dict[str, Any]]] = {}
    for model in (SMALL_V1, SMALL_V2, MEDIUM_V1):
        async with demo_target_client(model, "v1", "keyword") as target:
            bodies[model] = [(await chat(target, q)).json() for q in SEEDED_QUESTIONS]
    for index, question in enumerate(SEEDED_QUESTIONS):
        usages = [bodies[model][index]["usage"] for model in bodies]
        assert usages[0] == usages[1] == usages[2], (question, usages)
        small, medium = bodies[SMALL_V1][index], bodies[MEDIUM_V1][index]
        assert cost(medium) / cost(small) == Decimal("2.5"), question
        assert cost(bodies[SMALL_V2][index]) == cost(small), question


async def test_latency_is_simulated_never_waited() -> None:
    async with demo_target_client(MEDIUM_V1, "v1", "keyword") as target:
        for question in SEEDED_QUESTIONS[:5]:
            started = time.perf_counter()
            response = await chat(target, question)
            elapsed_ms = (time.perf_counter() - started) * 1000
            assert response.status_code == 200, response.text
            latency = response.json()["latency_ms"]
            assert MODELS[MEDIUM_V1].latency_min <= latency <= MODELS[MEDIUM_V1].latency_max
            assert elapsed_ms < latency, (question, elapsed_ms, latency)


async def test_question_length_is_admitted_from_one_to_two_thousand_characters() -> None:
    async with demo_target_client(*BASELINE) as target:
        for question in ("?", "a" * 2000, "é" * 2000, ANCHOR_QUESTION):
            response = await chat(target, question)
            assert response.status_code == 200, (len(question), response.text)
            assert_chat_shape(response.json(), SMALL_V1)
        for question in ("", "a" * 2001, "é" * 2001):
            response = await chat(target, question)
            assert_refused(response.status_code, response.content, f"length {len(question)}")


async def test_malformed_bodies_are_refused_without_an_answer() -> None:
    bodies: dict[str, Any] = {  # Any: deliberately ill-typed JSON values
        "missing-question": {},
        "extra-field": {"question": ANCHOR_QUESTION, "history": []},
        "null-question": {"question": None},
        "number-question": {"question": 5},
        "list-question": {"question": [ANCHOR_QUESTION]},
        "list-body": [ANCHOR_QUESTION],
        "string-body": ANCHOR_QUESTION,
    }
    async with demo_target_client(*BASELINE) as target:
        anchor = await chat(target, ANCHOR_QUESTION)
        assert anchor.status_code == 200, anchor.text
        for label, body in bodies.items():
            response = await target.post("/chat", json=body)
            assert_refused(response.status_code, response.content, label)
        for label, raw in (
            ("invalid-json", b'{"question": '),
            ("empty", b""),
            ("null-json", b"null"),
        ):
            response = await target.post(
                "/chat", content=raw, headers={"content-type": "application/json"}
            )
            assert_refused(response.status_code, response.content, label)
        after = await chat(target, ANCHOR_QUESTION)
        assert after.content == anchor.content  # refusals consumed nothing


@pytest.mark.parametrize(
    "config",
    [
        ("mock-gen-large-v9", "v1", "keyword"),
        ("", "v1", "keyword"),
        ("mock-gen-small-v1 ", "v1", "keyword"),
        (SMALL_V1, "v3", "keyword"),
        (SMALL_V1, "", "keyword"),
        (SMALL_V1, "1", "keyword"),
        (SMALL_V1, "v1", "hybrid"),
        (SMALL_V1, "v1", ""),
        (SMALL_V1, "v1", "Keyword"),
    ],
)
async def test_unknown_configuration_value_refuses_to_start(config: tuple[str, str, str]) -> None:
    factory = demo_target_factory()
    async with factory(*BASELINE) as target:  # anchor: a known configuration starts and answers
        assert (await chat(target, ANCHOR_QUESTION)).status_code == 200
    with pytest.raises(Exception):  # noqa: B017, PT011 — §6 fixes only "raises an exception"
        async with factory(*config):
            pytest.fail("a refused configuration was entered", pytrace=False)
