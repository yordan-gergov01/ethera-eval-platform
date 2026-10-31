"""Sealed oracle: Manifest schema problems and their dependency rules, via PUT.

Role: pins contract §3.3 "Schema", "Roles", "Allowed providers", "Full model ID" and
  "Problems"/"Dependent problems" of specs/001-product-registry/contract.md (INV-REG-01, -04,
  -05, -06, -09, -12, -13; C-7, C-8, C-9, C-10): each case states the exact SET of
  (field, type) pairs; boundaries are sealed at their own boundary (model 128/129, identifiers
  64/65, `v1`/`v0`/`v01`); valid documents are admitted with 201; the same document gives the
  same `errors` in the same order (§3.4); `message` never quotes a submitted value.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; _registry_oracle.py.
Key invariants: errors are compared as sets (the contract fixes no order) except in
  test_same_invalid_document_gives_the_same_errors_in_the_same_order; a binding that must stay
  valid uses `mock-gen-small-v1`, so only the planted defect can be reported; every refusal
  leaves version 1 in place.
"""

import pytest
from httpx import AsyncClient

from tests.integration.conftest import assert_problem
from tests.integration.registry._registry_oracle import (
    DEMO_DOCUMENT,
    LONGEST,
    TOO_LONG,
    Binding,
    admin_token,
    manifest_errors,
    manifest_text,
    put_manifest,
    read_manifest,
    with_model,
)

GEN: Binding = ("generation", "mock", "mock-gen-small-v1")
JUDGE: Binding = ("judge", "mock", "mock-judge-small-v1")
EMBED: Binding = ("embedding", "mock", "mock-embed-small-v1")
MODEL_128 = "mock-" + "a" * 114 + "-small-v1"
MODEL_129 = "mock-" + "a" * 115 + "-small-v1"
DROP_PRODUCT = "product:\n  client_id: acme\n  project_id: support-bot\n"


async def refused(api: AsyncClient, document: str) -> set[tuple[str, str]]:
    """The (field, type) pairs of the refusal as a set; asserts nothing changed."""
    admin = await admin_token(api)
    pairs = manifest_errors(await put_manifest(api, admin, 1, document))
    assert (await read_manifest(api, admin))["version"] == 1
    return set(pairs)


def without(document: str, text: str) -> str:
    assert text in document
    return document.replace(text, "")


CASES: dict[str, tuple[str, set[tuple[str, str]]]] = {
    # --- missing / unknown / wrong_type, with rule 2 (nothing checked inside) ---------------
    "product-missing": (without(DEMO_DOCUMENT, DROP_PRODUCT), {("product", "missing")}),
    "bindings-missing": (
        manifest_text().replace(
            "bindings:\n  - role: generation\n    provider: mock\n    model: mock-gen-small-v1\n",
            "",
        ),
        {("bindings", "missing")},
    ),
    "allowed-providers-missing": (
        without(DEMO_DOCUMENT, "allowed_providers:\n  - mock\n"),
        {("allowed_providers", "missing")},
    ),
    "project-id-missing": (
        without(DEMO_DOCUMENT, "  project_id: support-bot\n"),
        {("product.project_id", "missing")},
    ),
    "binding-model-missing": (
        without(DEMO_DOCUMENT, "    model: mock-gen-small-v1\n"),
        {("bindings[0].model", "missing")},
    ),
    "binding-provider-missing": (
        without(DEMO_DOCUMENT, "    provider: mock\n"),
        {("bindings[0].provider", "missing")},
    ),
    "binding-role-missing-no-generation-check": (
        DEMO_DOCUMENT.replace("  - role: generation\n    provider", "  - provider"),
        {("bindings[0].role", "missing")},
    ),
    "unknown-top-level-key": (manifest_text(extra="owner: team-a\n"), {("owner", "unknown_key")}),
    "unknown-product-key": (
        DEMO_DOCUMENT.replace(
            "  project_id: support-bot\n", "  project_id: support-bot\n  name: x\n"
        ),
        {("product.name", "unknown_key")},
    ),
    "unknown-binding-key": (
        DEMO_DOCUMENT.replace("    model:", "    temperature: hot\n    model:"),
        {("bindings[0].temperature", "unknown_key")},
    ),
    "product-wrong-type": (
        DEMO_DOCUMENT.replace(DROP_PRODUCT, "product: acme/support-bot\n"),
        {("product", "wrong_type")},
    ),
    "client-id-wrong-type": (manifest_text(client_id="1"), {("product.client_id", "wrong_type")}),
    "bindings-wrong-type": (
        manifest_text(bindings=[]).replace("bindings: []", "bindings: generation"),
        {("bindings", "wrong_type")},
    ),
    "binding-not-a-mapping": (
        manifest_text(bindings=[]).replace("bindings: []", "bindings: [generation]"),
        {("bindings[0]", "wrong_type")},
    ),
    "allowed-providers-wrong-type": (
        manifest_text(allowed=[]).replace("allowed_providers: []", "allowed_providers: mock"),
        {("allowed_providers", "wrong_type")},
    ),
    "allowed-provider-element-wrong-type": (
        manifest_text(allowed=["mock", "1"]),
        {("allowed_providers[1]", "wrong_type")},
    ),
    "role-wrong-type": (
        manifest_text(bindings=[("yes", "mock", "mock-gen-small-v1")]),
        {("bindings[0].role", "wrong_type")},
    ),
    "model-unquoted-empty": (with_model(""), {("bindings[0].model", "wrong_type")}),
    # --- invalid_value -----------------------------------------------------------------------
    "allowed-providers-empty": (
        manifest_text(allowed=[]),
        {("allowed_providers", "invalid_value")},
    ),
    "role-outside-the-set": (
        manifest_text(bindings=[GEN, ("critic", "mock", "mock-judge-small-v1")]),
        {("bindings[1].role", "invalid_value")},
    ),
    "role-outside-the-set-alone": (
        manifest_text(bindings=[("critic", "mock", "mock-judge-small-v1")]),
        {("bindings[0].role", "invalid_value")},
    ),
    "role-wrong-case": (
        manifest_text(bindings=[("Generation", "mock", "mock-gen-small-v1")]),
        {("bindings[0].role", "invalid_value")},
    ),
    "model-quoted-empty": (with_model('""'), {("bindings[0].model", "invalid_value")}),
    "model-129-chars": (with_model(MODEL_129), {("bindings[0].model", "invalid_value")}),
    # --- identifiers, rule 6 ----------------------------------------------------------------
    "client-id-upper-case": (
        manifest_text(client_id="ACME"),
        {("product.client_id", "invalid_value")},
    ),
    "client-id-65-chars": (
        manifest_text(client_id=TOO_LONG),
        {("product.client_id", "invalid_value")},
    ),
    "client-id-quoted-empty": (
        manifest_text(client_id='""'),
        {("product.client_id", "invalid_value")},
    ),
    "project-id-trailing-hyphen": (
        manifest_text(project_id="support-bot-"),
        {("product.project_id", "invalid_value")},
    ),
    "project-id-underscore": (
        manifest_text(project_id="support_bot"),
        {("product.project_id", "invalid_value")},
    ),
    "client-id-other-client": (
        manifest_text(client_id="globex"),
        {("product.client_id", "product_mismatch")},
    ),
    "client-id-64-chars": (
        manifest_text(client_id=LONGEST),
        {("product.client_id", "product_mismatch")},
    ),
    "both-ids-other-product": (
        manifest_text(client_id="globex", project_id="portal"),
        {("product.client_id", "product_mismatch"), ("product.project_id", "product_mismatch")},
    ),
    # --- alias (C-9) and rule 3 -------------------------------------------------------------
    "model-latest": (with_model("mock-gen-small-latest"), {("bindings[0].model", "alias")}),
    "model-no-version": (with_model("mock-gen-small"), {("bindings[0].model", "alias")}),
    "model-v0": (with_model("mock-gen-small-v0"), {("bindings[0].model", "alias")}),
    "model-v01": (with_model("mock-gen-small-v01"), {("bindings[0].model", "alias")}),
    "model-digit-in-family": (with_model("mock-gen2-small-v1"), {("bindings[0].model", "alias")}),
    "model-upper-case": (with_model("Mock-gen-small-v1"), {("bindings[0].model", "alias")}),
    "model-other-vendor-name": (with_model("gpt-4o"), {("bindings[0].model", "alias")}),
    # --- providers, rule 5 ------------------------------------------------------------------
    "binding-provider-unknown-and-not-allowed": (
        manifest_text(bindings=[("generation", "openai", "gpt-4o")]),
        {
            ("bindings[0].provider", "unknown_provider"),
            ("bindings[0].provider", "provider_not_allowed"),
        },
    ),
    "unknown-provider-listed-too": (
        manifest_text(bindings=[("generation", "openai", "gpt-4o")], allowed=["mock", "openai"]),
        {
            ("bindings[0].provider", "unknown_provider"),
            ("allowed_providers[1]", "unknown_provider"),
        },
    ),
    "known-provider-not-allowed": (
        manifest_text(allowed=["openai"]),
        {
            ("allowed_providers[0]", "unknown_provider"),
            ("bindings[0].provider", "provider_not_allowed"),
        },
    ),
    "allowed-providers-duplicates": (
        manifest_text(allowed=["mock", "mock", "mock"]),
        {("allowed_providers[1]", "duplicate_value"), ("allowed_providers[2]", "duplicate_value")},
    ),
    "provider-wrong-type-not-checked-against-list": (
        manifest_text(bindings=[("generation", "1", "mock-gen-small-v1")]),
        {("bindings[0].provider", "wrong_type")},
    ),
    # --- roles, rule 4 ----------------------------------------------------------------------
    "bindings-empty": (manifest_text(bindings=[]), {("bindings", "generation_required")}),
    "judge-only": (manifest_text(bindings=[JUDGE]), {("bindings", "generation_required")}),
    "three-generations": (
        manifest_text(bindings=[GEN, GEN, GEN]),
        {("bindings[1].role", "duplicate_role"), ("bindings[2].role", "duplicate_role")},
    ),
    "second-judge": (
        manifest_text(bindings=[GEN, JUDGE, JUDGE]),
        {("bindings[2].role", "duplicate_role")},
    ),
    "two-embeddings-no-generation": (
        manifest_text(bindings=[EMBED, EMBED]),
        {("bindings[1].role", "duplicate_role"), ("bindings", "generation_required")},
    ),
    "role-checks-skipped-when-a-binding-is-not-a-mapping": (
        manifest_text(bindings=[JUDGE]).replace(
            "allowed_providers:", "  - judge\nallowed_providers:"
        ),
        {("bindings[1]", "wrong_type")},
    ),
    # --- independent causes are all reported (FR-004, SC-004) -------------------------------
    "three-independent-causes": (
        manifest_text(
            bindings=[("generation", "mock", "mock-gen-small")],
            allowed=["mock", "mock"],
            extra="owner: team-a\n",
        ),
        {
            ("bindings[0].model", "alias"),
            ("allowed_providers[1]", "duplicate_value"),
            ("owner", "unknown_key"),
        },
    ),
}


@pytest.mark.parametrize("case", sorted(CASES))
async def test_invalid_manifest_reports_exactly_its_problems(api: AsyncClient, case: str) -> None:
    document, expected = CASES[case]
    assert await refused(api, document) == expected


ADMITTED: dict[str, str] = {
    "model-128-chars": with_model(MODEL_128),
    "model-v12": with_model("mock-gen-large-v12"),
    "model-v1-other-size": with_model("mock-gen-large-v1"),
    "all-three-roles": manifest_text(bindings=[GEN, JUDGE, EMBED]),
    "generation-not-first": manifest_text(bindings=[EMBED, GEN]),
}


@pytest.mark.parametrize("case", sorted(ADMITTED))
async def test_valid_manifest_is_admitted_as_the_next_version(api: AsyncClient, case: str) -> None:
    admin = await admin_token(api)
    response = await put_manifest(api, admin, 1, ADMITTED[case])
    assert response.status_code == 201, response.text
    assert response.json()["version"] == 2
    assert (await read_manifest(api, admin))["document"] == ADMITTED[case]


async def test_same_invalid_document_gives_the_same_errors_in_the_same_order(
    api: AsyncClient,
) -> None:
    admin = await admin_token(api)
    document = CASES["three-independent-causes"][0]
    first = (await put_manifest(api, admin, 1, document)).json()
    second = (await put_manifest(api, admin, 1, document)).json()
    assert first["code"] == second["code"] == "MANIFEST_INVALID"
    assert len(first["errors"]) == 3
    assert first["errors"] == second["errors"]


async def test_problem_messages_never_quote_a_submitted_value(api: AsyncClient) -> None:
    admin = await admin_token(api)
    document = manifest_text(
        client_id="qzclientmarker",
        bindings=[("generation", "mock", "mock-gen-small-qzmodelmarker")],
        allowed=["mock", "qzprovidermarker"],
    )
    body = assert_problem(await put_manifest(api, admin, 1, document), 422, "MANIFEST_INVALID")
    assert {(e["field"], e["type"]) for e in body["errors"]} == {
        ("product.client_id", "product_mismatch"),
        ("bindings[0].model", "alias"),
        ("allowed_providers[1]", "unknown_provider"),
    }
    for error in body["errors"]:
        for marker in ("qzclientmarker", "qzmodelmarker", "qzprovidermarker"):
            assert marker not in error["message"], error
