"""Sealed oracle: Golden content never reaches the backend logs; the demo target logs no text.

Role: pins §5 "Logs" of specs/002-demo-target-and-dataset/contract.md (C-214; never-log list of
  .claude/rules/observability.md): markers planted in an arranged Golden's `input`, `rule`,
  `context` and `expected_numbers` never appear in the captured backend output while the
  requests that returned them succeeded; the demo target's logs hold no `question` and no
  `answer`, on answered and on refused questions.
Used by: pytest (integration; needs the test database and broker).
Depends on: `backend_settings` and `capsys`; the slice 001 helper `platform_app` through
  tests/integration/registry/_contract_fixtures.py; the §6 helpers `arrange_dataset_version` and
  `demo_target_logs` through _contract_fixtures.py; _evaluation_oracle.py.
Key invariants: the platform app is entered INSIDE the test after `capsys` replaced stdout, so
  the real handler writes into the capture; each marker is first seen in a 200 body (anti-
  vacuity) and the capture is proven live by the app's own request lines; the demo target's
  capture cannot be proven non-empty (the contract does not require it to log), so its anchor
  is the 200 that carried the marker and the non-empty answer it returned.
"""

import json
from typing import Any

import pytest

from tests.integration.conftest import bearer
from tests.integration.evaluation._contract_fixtures import (
    arrange_dataset_version,
    demo_target_logs,
)
from tests.integration.evaluation._evaluation_oracle import (
    BASELINE,
    SEEDED_QUESTIONS,
    chat,
    dataset_path,
    golden,
    read_version,
    version_path,
)
from tests.integration.registry._contract_fixtures import platform_app
from tests.integration.registry._registry_oracle import ACME, SUPPORT_BOT, admin_token

INPUT_MARKER = "qzgoldeninputmarker"
RULE_MARKER = "qzgoldenrulemarker"
CONTEXT_MARKER = "qzgoldencontextmarker"
NUMBER_MARKER = "73519.0846"
QUESTION_MARKER = "qzchatquestionmarker"


async def test_golden_content_never_reaches_the_backend_logs(
    backend_settings: Any,  # Any: opaque settings
    capsys: pytest.CaptureFixture[str],
) -> None:
    arranged = golden(
        f"Can I return {INPUT_MARKER} boots?",
        rule=f"Rule {RULE_MARKER} — doc returns",
        context=f"Context {CONTEXT_MARKER}",
        expected_numbers=(NUMBER_MARKER,),
    )
    async with platform_app(backend_settings) as api:
        admin = await admin_token(api)
        number = await arrange_dataset_version(backend_settings, ACME, SUPPORT_BOT, [arranged])
        assert number == 2
        version = await read_version(api, admin, 2)
        text = json.dumps(version)
        for marker in (INPUT_MARKER, RULE_MARKER, CONTEXT_MARKER, NUMBER_MARKER):
            assert marker in text, marker  # anchor: the request that returned it succeeded
        summary = await api.get(dataset_path(), headers=bearer(admin))
        assert summary.status_code == 200, summary.text
        seeded = await api.get(version_path(1), headers=bearer(admin))
        assert seeded.status_code == 200, seeded.text
    output = capsys.readouterr().out

    access = [line for line in output.splitlines() if line.startswith("{") and "/dataset" in line]
    assert access, "anti-vacuity: the Dataset requests left no line in the capture"
    leaked = [
        marker
        for marker in (INPUT_MARKER, RULE_MARKER, CONTEXT_MARKER, NUMBER_MARKER)
        if marker in output
    ]
    assert leaked == [], leaked
    for question in SEEDED_QUESTIONS:
        assert question not in output, question


async def test_demo_target_logs_no_question_and_no_answer() -> None:
    answered = f"Can I return these {QUESTION_MARKER} shoes I got 10 days ago?"
    refused = f"{QUESTION_MARKER}refused " + "x" * 2001
    async with demo_target_logs(*BASELINE) as (target, logs):
        answers = []
        for question in (answered, *SEEDED_QUESTIONS):
            response = await chat(target, question)
            assert response.status_code == 200, response.text  # anchor
            answer = response.json()["answer"]
            assert isinstance(answer, str)
            assert answer
            answers.append(answer)
        assert (await chat(target, refused)).status_code == 422
        output = logs()
    assert isinstance(output, str)
    assert QUESTION_MARKER not in output
    for question in SEEDED_QUESTIONS:
        assert question not in output, question
    for answer in answers:
        if len(answer) >= 12:  # a long-enough answer cannot occur in a log line by chance
            assert answer not in output, answer
