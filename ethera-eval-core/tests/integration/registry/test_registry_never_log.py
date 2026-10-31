"""Sealed oracle: Manifest content never reaches the technical logs; the two events are emitted.

Role: pins contract §5 "Logs" of specs/001-product-registry/contract.md (C-13; never-log list of
  .claude/rules/observability.md): one `manifest_replaced` line per 201, one `manifest_refused`
  line per MANIFEST_INVALID with an integer `problem_count` equal to the length of `errors`, no
  username or email on either event, and no planted marker (model value, YAML comment,
  identifier, malformed text, oversized document) anywhere in the captured output.
Used by: pytest (integration; needs the test database and broker).
Depends on: `backend_settings` from tests/integration/conftest.py; the §6 helpers
  `platform_app` and `arrange_membership` through _contract_fixtures.py; _registry_oracle.py;
  `capsys`, as in tests/integration/test_never_log.py.
Key invariants: the app is entered INSIDE each test after `capsys` replaced stdout, so the real
  handler writes into the capture; every request's status is asserted and the events are
  required present (anti-vacuity); event counts use only 201 and MANIFEST_INVALID requests,
  the only ones whose log lines the contract fixes.
"""

import json
from typing import Any

import pytest

from tests.integration.conftest import assert_problem
from tests.integration.registry._contract_fixtures import arrange_membership, platform_app
from tests.integration.registry._registry_oracle import (
    ACME,
    DEMO_DOCUMENT,
    admin_token,
    manifest_errors,
    manifest_text,
    new_user,
    put_manifest,
    validation_fields,
    with_model,
)

CALLER = "quillon"
CALLER_EMAIL = f"{CALLER}@example.com"
COMMENT_MARKER = "qzcommentmarker"
MODEL_MARKER = "qzmodelmarker"


def log_lines(output: str) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for raw in output.splitlines():
        try:
            parsed = json.loads(raw)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            lines.append(parsed)
    return lines


def events(output: str, name: str) -> list[dict[str, Any]]:
    return [line for line in log_lines(output) if line.get("event") == name]


async def test_events_are_emitted_once_per_outcome_without_identity(
    backend_settings: Any,  # Any: opaque settings
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with platform_app(backend_settings) as api:
        await admin_token(api)
        caller = await new_user(api, backend_settings, CALLER, "admin")
        await arrange_membership(backend_settings, CALLER, ACME)
        for base, model in ((1, "mock-gen-large-v2"), (2, "mock-gen-large-v3")):
            response = await put_manifest(api, caller, base, with_model(model))
            assert response.status_code == 201, response.text
        counts = []
        for document in (
            with_model("mock-gen-small-latest"),
            manifest_text(allowed=["mock", "mock", "mock"], extra="owner: x\n"),
        ):
            counts.append(len(manifest_errors(await put_manifest(api, caller, 3, document))))
    output = capsys.readouterr().out

    replaced = events(output, "manifest_replaced")
    refused = events(output, "manifest_refused")
    assert len(replaced) == 2
    assert len(refused) == 2
    problem_counts = [line.get("problem_count") for line in refused]
    assert all(isinstance(n, int) and not isinstance(n, bool) for n in problem_counts)
    assert problem_counts == counts == [1, 3]
    for line in replaced + refused:
        text = json.dumps(line)
        assert CALLER not in text, line
        assert CALLER_EMAIL not in text, line


async def test_manifest_content_never_reaches_the_logs(
    backend_settings: Any,  # Any: opaque settings
    capsys: pytest.CaptureFixture[str],
) -> None:
    markers = {
        "accepted-comment": f"{COMMENT_MARKER}a",
        "accepted-model": f"{MODEL_MARKER}a",
        "refused-comment": f"{COMMENT_MARKER}b",
        "refused-model": f"{MODEL_MARKER}b",
        "refused-identifier": "qzidentifiermarker",
        "malformed-text": "qzmalformedmarker",
        "equal-comment": f"{COMMENT_MARKER}c",
        "oversized-text": "qzoversizedmarker",
        "conflict-model": f"{MODEL_MARKER}c",
    }
    async with platform_app(backend_settings) as api:
        await admin_token(api)
        caller = await new_user(api, backend_settings, CALLER, "admin")
        await arrange_membership(backend_settings, CALLER, ACME)

        accepted = f"# {markers['accepted-comment']}\n" + with_model(
            f"mock-{markers['accepted-model']}-small-v1"
        )
        assert (await put_manifest(api, caller, 1, accepted)).status_code == 201
        equal = f"# {markers['equal-comment']}\n" + accepted
        assert (await put_manifest(api, caller, 2, equal)).status_code == 200
        refused = f"# {markers['refused-comment']}\n" + manifest_text(
            client_id=markers["refused-identifier"],
            bindings=[("generation", "mock", f"mock-gen-small-{markers['refused-model']}")],
        )
        assert len(manifest_errors(await put_manifest(api, caller, 2, refused))) == 2
        malformed = f"product: [{markers['malformed-text']}\nbindings: {{\n"
        assert manifest_errors(await put_manifest(api, caller, 2, malformed)) == [
            ("document", "malformed")
        ]
        oversized = DEMO_DOCUMENT + f"# {markers['oversized-text']} " + "x" * 32_800 + "\n"
        assert "body.document" in validation_fields(await put_manifest(api, caller, 2, oversized))
        conflict = with_model(f"mock-{markers['conflict-model']}-small-v1")
        response = await put_manifest(api, caller, 1, conflict)
        assert_problem(response, 409, "MANIFEST_VERSION_CONFLICT")
    output = capsys.readouterr().out

    assert events(output, "manifest_replaced"), "anti-vacuity: the accepted PUT logged nothing"
    assert events(output, "manifest_refused"), "anti-vacuity: the refusals logged nothing"
    leaked = {name: marker for name, marker in markers.items() if marker in output}
    assert leaked == {}, [
        line for line in output.splitlines() if any(m in line for m in leaked.values())
    ]
