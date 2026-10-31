"""Sealed oracle: document-level Manifest problems and YAML 1.1 scalar typing, via PUT.

Role: pins contract §3.3 "Document level" and "Scalars" of specs/001-product-registry/contract.md
  (D-018, C-5, C-6, C-11): `malformed`, `unsupported_syntax` and `duplicate_key` each reported
  alone with no schema check after them; nesting admitted at 10 levels and refused at 11; every
  plain-scalar token of the contract typed as listed, observed through `bindings[0].model`
  (a non-string is `wrong_type`, a string that is no full model ID is `alias`) and as a key.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; _registry_oracle.py.
Key invariants: each document carries exactly ONE document-level defect (the contract leaves the
  choice among several unsealed); the 10-level case nests inside a value that is `wrong_type`,
  whose contents the contract says are never checked, so its answer is fully determined; every
  case also proves the refusal left version 1 in place.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient

from tests.integration.registry._registry_oracle import (
    DEMO_DOCUMENT,
    admin_token,
    manifest_errors,
    manifest_text,
    put_manifest,
    read_manifest,
    with_model,
)

MODEL = "bindings[0].model"


async def refused(api: AsyncClient, document: str) -> list[tuple[str, str]]:
    """The (field, type) pairs of the refusal; asserts nothing changed."""
    admin = await admin_token(api)
    pairs = manifest_errors(await put_manifest(api, admin, 1, document))
    assert (await read_manifest(api, admin))["version"] == 1
    return pairs


def nested_lists(depth: int) -> str:
    """A `product` value of nested flow lists; the document's depth is `depth`."""
    lists = depth - 1  # the top-level mapping is level 1, each list adds one
    return DEMO_DOCUMENT.replace(
        "product:\n  client_id: acme\n  project_id: support-bot\n",
        "product: " + "[" * lists + "x" + "]" * lists + "\n",
    )


def nested_mixed(depth: int) -> str:
    """Alternating flow lists and mappings under `product`, starting with a list."""
    value = "x"
    for level in range(depth - 1, 0, -1):
        value = f"[{value}]" if level % 2 == 1 else f"{{k: {value}}}"
    return DEMO_DOCUMENT.replace(
        "product:\n  client_id: acme\n  project_id: support-bot\n", f"product: {value}\n"
    )


@pytest.mark.parametrize(
    "builder", [pytest.param(nested_lists, id="lists"), pytest.param(nested_mixed, id="mixed")]
)
async def test_nesting_of_10_levels_is_admitted_and_11_is_malformed(
    api: AsyncClient, builder: Callable[[int], str]
) -> None:
    assert await refused(api, builder(10)) == [("product", "wrong_type")]
    assert await refused(api, builder(11)) == [("document", "malformed")]


DOCUMENT_LEVEL: dict[str, tuple[str, str]] = {
    # malformed
    "not-yaml": ("product: [unclosed\nbindings: {\n", "malformed"),
    "two-documents": (DEMO_DOCUMENT + "---\n" + DEMO_DOCUMENT, "malformed"),
    "top-level-list": ("- product\n- bindings\n", "malformed"),
    "top-level-scalar": ("support-bot", "malformed"),
    "comment-only": ("# nothing but a comment\n", "malformed"),
    # unsupported_syntax
    "anchor": (
        DEMO_DOCUMENT.replace("allowed_providers:\n", "allowed_providers: &providers\n"),
        "unsupported_syntax",
    ),
    "anchor-and-alias": (
        DEMO_DOCUMENT.replace("    provider: mock\n", "    provider: &p mock\n").replace(
            "  - mock\n", "  - *p\n"
        ),
        "unsupported_syntax",
    ),
    "merge-key": (
        DEMO_DOCUMENT.replace("  - role: generation\n", "  - <<: {role: generation}\n"),
        "unsupported_syntax",
    ),
    "core-tag": (with_model("!!str mock-gen-small-v1"), "unsupported_syntax"),
    "local-tag": (with_model("!model mock-gen-small-v1"), "unsupported_syntax"),
    "key-on": (DEMO_DOCUMENT + "on: 1\n", "unsupported_syntax"),
    "key-yes": (DEMO_DOCUMENT + "yes: 1\n", "unsupported_syntax"),
    "key-integer": (DEMO_DOCUMENT + "1: x\n", "unsupported_syntax"),
    "key-float": (DEMO_DOCUMENT + "1.5: x\n", "unsupported_syntax"),
    "key-null": (DEMO_DOCUMENT + "~: x\n", "unsupported_syntax"),
    "key-date": (DEMO_DOCUMENT + "2026-10-30: x\n", "unsupported_syntax"),
    "key-complex": (DEMO_DOCUMENT + "? [a]\n: b\n", "unsupported_syntax"),
    "nested-non-string-key": (
        DEMO_DOCUMENT.replace("  project_id: support-bot\n", "  project_id: support-bot\n  1: x\n"),
        "unsupported_syntax",
    ),
}


@pytest.mark.parametrize("case", sorted(DOCUMENT_LEVEL))
async def test_document_level_problem_is_reported_alone(api: AsyncClient, case: str) -> None:
    document, problem = DOCUMENT_LEVEL[case]
    assert await refused(api, document) == [("document", problem)]


DUPLICATE_KEYS: dict[str, tuple[str, str]] = {
    "product-client-id": (
        DEMO_DOCUMENT.replace("  client_id: acme\n", "  client_id: acme\n  client_id: acme\n"),
        "product.client_id",
    ),
    "binding-role": (
        DEMO_DOCUMENT.replace("  - role: generation\n", "  - role: generation\n    role: judge\n"),
        "bindings[0].role",
    ),
    "top-level": (DEMO_DOCUMENT + "allowed_providers:\n  - mock\n", "allowed_providers"),
}


@pytest.mark.parametrize("case", sorted(DUPLICATE_KEYS))
async def test_duplicate_key_is_reported_alone_at_its_path(api: AsyncClient, case: str) -> None:
    document, field = DUPLICATE_KEYS[case]
    assert await refused(api, document) == [(field, "duplicate_key")]


NOT_STRINGS = [
    *("true", "True", "TRUE", "false", "False", "FALSE"),
    *("yes", "Yes", "YES", "no", "No", "NO"),
    *("on", "On", "ON", "off", "Off", "OFF"),
    *("~", "null", "Null", "NULL", ""),
    *("1", "010", "0x1f", "1_000", "1:30"),
    *("1.5", "1.0e+3", ".inf"),
    *("2026-10-30", "2026-10-30 10:00:00"),
]


@pytest.mark.parametrize("token", NOT_STRINGS, ids=lambda t: f"plain[{t}]")
async def test_plain_scalar_that_is_not_a_string_is_wrong_type(
    api: AsyncClient, token: str
) -> None:
    assert await refused(api, with_model(token)) == [(MODEL, "wrong_type")]


STRINGS = ["tRuE", "y", "n", "1e3", "'yes'", '"1"', "'~'", "'2026-10-30'", '"on"', "'1.5'"]


@pytest.mark.parametrize("token", STRINGS, ids=lambda t: f"string[{t}]")
async def test_string_scalar_reaches_the_model_id_check(api: AsyncClient, token: str) -> None:
    assert await refused(api, with_model(token)) == [(MODEL, "alias")]


async def test_quoted_empty_model_is_invalid_value(api: AsyncClient) -> None:
    assert await refused(api, with_model('""')) == [(MODEL, "invalid_value")]


@pytest.mark.parametrize(
    ("key", "field"),
    [("y", "y"), ("n", "n"), ("tRuE", "tRuE"), ("'on'", "on"), ('"1"', "1"), ("'~'", "~")],
)
async def test_string_key_outside_the_schema_is_unknown_key(
    api: AsyncClient, key: str, field: str
) -> None:
    assert await refused(api, manifest_text(extra=f"{key}: x\n")) == [(field, "unknown_key")]
