"""Sealed oracle: PUT .../manifest — new versions, equal Manifests, shape and response order.

Role: pins contract §2.3 and §3.2 of specs/001-product-registry/contract.md — 201 with
  version = current + 1 and `created_by` = the caller, gap-free numbering, the 200 for an equal
  Manifest (C-4), the request-shape bounds (C-3), and the order of the response table, one test
  per adjacent pair of rows.
Used by: pytest (integration; needs the test database and broker).
Depends on: `api` from tests/integration/registry/conftest.py; `backend_settings` from
  tests/integration/conftest.py; _registry_oracle.py; the §6 helpers through
  _contract_fixtures.py.
Key invariants: every refusal test also proves an accepted replacement on the same route (or a
  200 read of the target), so a missing route can never pass; documents are ASCII, so their
  length in characters is their length in bytes.
"""

from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.conftest import assert_problem, bearer
from tests.integration.registry._contract_fixtures import arrange_membership, read_audit_rows
from tests.integration.registry._registry_oracle import (
    ACME,
    DEMO_DOCUMENT,
    LONGEST,
    SUPPORT_BOT,
    TOO_LONG,
    admin_token,
    arrange_member_product,
    assert_offset_timestamp,
    manifest_path,
    manifest_text,
    new_user,
    not_found_body,
    put_manifest,
    read_manifest,
    validation_fields,
    with_model,
)

NEW_MODEL = "mock-gen-large-v2"
MAX_DOCUMENT = 32_768


def padded(document: str, length: int) -> str:
    """`document` followed by a YAML comment that brings it to exactly `length` characters."""
    filler = length - len(document) - len("# \n")
    padded_text = document + "# " + "x" * filler + "\n"
    assert len(padded_text) == length
    return padded_text


async def _accepted(api: AsyncClient, token: str, base: int, document: str) -> dict[str, Any]:
    response = await put_manifest(api, token, base, document)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_replace_creates_the_next_version_by_the_caller(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    erin = await new_user(api, backend_settings, "erin", "admin")
    await arrange_membership(backend_settings, "erin", ACME)
    seeded = await read_manifest(api, erin)
    document = with_model(NEW_MODEL)

    created = await _accepted(api, erin, 1, document)
    assert_offset_timestamp(created.pop("created_at"))
    assert created == {
        "version": 2,
        "bindings": [{"role": "generation", "provider": "mock", "model": NEW_MODEL}],
        "allowed_providers": ["mock"],
        "document": document,
        "created_by": "erin",
    }
    current = await read_manifest(api, admin)
    assert current["version"] == 2
    assert current["document"] == document
    assert current["created_by"] == "erin"
    created_at = datetime.fromisoformat(current["created_at"])
    assert created_at >= datetime.fromisoformat(seeded["created_at"])


async def test_versions_increase_by_one_without_gaps(api: AsyncClient) -> None:
    admin = await admin_token(api)
    for base, model in ((1, "mock-gen-large-v2"), (2, "mock-gen-large-v3"), (3, "mock-gen-x-v4")):
        assert (await _accepted(api, admin, base, with_model(model)))["version"] == base + 1
    stale = await put_manifest(api, admin, 3, with_model("mock-gen-large-v5"))
    assert_problem(stale, 409, "MANIFEST_VERSION_CONFLICT")
    assert (await read_manifest(api, admin))["version"] == 4


async def test_reordered_bindings_make_a_new_version(api: AsyncClient) -> None:
    admin = await admin_token(api)
    judge = ("judge", "mock", "mock-judge-small-v1")
    generation = ("generation", "mock", "mock-gen-small-v1")
    await _accepted(api, admin, 1, manifest_text(bindings=[generation, judge]))
    reordered = await _accepted(api, admin, 2, manifest_text(bindings=[judge, generation]))
    assert reordered["version"] == 3
    assert [b["role"] for b in reordered["bindings"]] == ["judge", "generation"]


EQUAL_VARIANTS = {
    "comment": "# reviewed, nothing to change\n" + DEMO_DOCUMENT + "# end\n",
    "whitespace": (
        DEMO_DOCUMENT.replace("\n  ", "\n    ")
        .replace(":\n", ":   \n")
        .replace("\nbindings", "\n\n\nbindings")
        .replace("\nallowed_providers", "\n\nallowed_providers")
    ),
    "quoting": DEMO_DOCUMENT.replace("acme", "'acme'").replace(
        "mock-gen-small-v1", '"mock-gen-small-v1"'
    ),
    "key-order": (
        "allowed_providers:\n  - mock\n"
        "bindings:\n  - model: mock-gen-small-v1\n    provider: mock\n    role: generation\n"
        "product:\n  project_id: support-bot\n  client_id: acme\n"
    ),
    "flow-style": (
        "{product: {client_id: acme, project_id: support-bot}, "
        "bindings: [{role: generation, provider: mock, model: mock-gen-small-v1}], "
        "allowed_providers: [mock]}"
    ),
}


@pytest.mark.parametrize("variant", sorted(EQUAL_VARIANTS))
async def test_equal_manifest_returns_the_current_version_unchanged(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
    variant: str,
) -> None:
    admin = await admin_token(api)
    before = await read_manifest(api, admin)
    rows_before = len(await read_audit_rows(backend_settings))

    response = await put_manifest(api, admin, 1, EQUAL_VARIANTS[variant])

    assert response.status_code == 200, response.text
    assert response.json() == before
    assert await read_manifest(api, admin) == before
    assert len(await read_audit_rows(backend_settings)) == rows_before
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


async def test_document_of_32768_characters_is_admitted(api: AsyncClient) -> None:
    admin = await admin_token(api)
    document = padded(with_model(NEW_MODEL), MAX_DOCUMENT)
    created = await _accepted(api, admin, 1, document)
    assert created["document"] == document
    assert (await read_manifest(api, admin))["document"] == document


async def test_document_of_one_character_reaches_manifest_validation(api: AsyncClient) -> None:
    admin = await admin_token(api)
    response = await put_manifest(api, admin, 1, "a")
    body = assert_problem(response, 422, "MANIFEST_INVALID")
    assert [(e["field"], e["type"]) for e in body["errors"]] == [("document", "malformed")]


SHAPE_VIOLATIONS: dict[str, tuple[Any, str]] = {
    "base-version-missing": ({"document": DEMO_DOCUMENT}, "body.base_version"),
    "base-version-zero": ({"base_version": 0, "document": DEMO_DOCUMENT}, "body.base_version"),
    "base-version-negative": (
        {"base_version": -1, "document": DEMO_DOCUMENT},
        "body.base_version",
    ),
    "base-version-null": ({"base_version": None, "document": DEMO_DOCUMENT}, "body.base_version"),
    "document-missing": ({"base_version": 1}, "body.document"),
    "document-empty": ({"base_version": 1, "document": ""}, "body.document"),
    "document-32769": (
        {"base_version": 1, "document": padded(with_model(NEW_MODEL), MAX_DOCUMENT + 1)},
        "body.document",
    ),
    "document-not-a-string": ({"base_version": 1, "document": 7}, "body.document"),
    "document-null": ({"base_version": 1, "document": None}, "body.document"),
    "unknown-field": (
        {"base_version": 1, "document": with_model(NEW_MODEL), "comment": "x"},
        "body.comment",
    ),
}


@pytest.mark.parametrize("case", sorted(SHAPE_VIOLATIONS))
async def test_body_shape_violation_is_validation_failed_and_changes_nothing(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
    case: str,
) -> None:
    admin = await admin_token(api)
    before = await read_manifest(api, admin)
    rows_before = len(await read_audit_rows(backend_settings))
    body, field = SHAPE_VIOLATIONS[case]

    response = await api.put(manifest_path(), json=body, headers=bearer(admin))

    assert field in validation_fields(response)
    assert await read_manifest(api, admin) == before
    assert len(await read_audit_rows(backend_settings)) == rows_before
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


async def test_replace_requires_a_token(api: AsyncClient) -> None:
    admin = await admin_token(api)
    assert_problem(
        await put_manifest(api, None, 1, with_model(NEW_MODEL)), 401, "AUTHENTICATION_FAILED"
    )
    bad = await put_manifest(api, "not-a-token", 1, with_model(NEW_MODEL))
    assert_problem(bad, 401, "INVALID_TOKEN")
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


async def test_member_without_manifests_write_is_permission_denied(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    mira = await new_user(api, backend_settings, "mira", "user")
    await arrange_membership(backend_settings, "mira", ACME)
    assert (await read_manifest(api, mira))["version"] == 1
    for client_id, project_id in ((ACME, SUPPORT_BOT), ("no-such-client", "no-such-bot")):
        response = await put_manifest(
            api, mira, 1, with_model(NEW_MODEL), client_id=client_id, project_id=project_id
        )
        assert_problem(response, 403, "PERMISSION_DENIED")
    assert (await read_manifest(api, mira))["version"] == 1
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


# --- The order of the response table (§2.3), one test per adjacent pair ----------------


async def test_malformed_json_is_400_before_authentication_and_authorization(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    mira = await new_user(api, backend_settings, "mira", "user")
    for headers in ({}, bearer("not-a-token"), bearer(mira), bearer(admin)):
        response = await api.put(
            manifest_path(),
            content=b'{"base_version": 1, "document": ',
            headers=headers | {"Content-Type": "application/json"},
        )
        assert_problem(response, 400, "MALFORMED_REQUEST")
    assert (await read_manifest(api, admin))["version"] == 1
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


async def test_missing_token_is_401_before_body_shape(api: AsyncClient) -> None:
    admin = await admin_token(api)
    response = await api.put(manifest_path(), json={"base_version": 0})
    assert_problem(response, 401, "AUTHENTICATION_FAILED")
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


async def test_permission_is_checked_before_body_shape(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    admin = await admin_token(api)
    mira = await new_user(api, backend_settings, "mira", "user")
    await arrange_membership(backend_settings, "mira", ACME)
    response = await api.put(manifest_path(), json={"base_version": 0}, headers=bearer(mira))
    assert_problem(response, 403, "PERMISSION_DENIED")
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


@pytest.mark.parametrize(
    ("client_id", "project_id"),
    [
        pytest.param(ACME, "no-such-bot", id="missing-product"),
        pytest.param("Acme", SUPPORT_BOT, id="off-pattern-segment"),
    ],
)
async def test_body_shape_is_checked_before_the_product_lookup(
    api: AsyncClient, client_id: str, project_id: str
) -> None:
    admin = await admin_token(api)
    response = await api.put(
        manifest_path(client_id, project_id),
        json={"base_version": 1, "document": ""},
        headers=bearer(admin),
    )
    assert "body.document" in validation_fields(response)
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


async def test_missing_product_is_404_before_version_conflict(api: AsyncClient) -> None:
    admin = await admin_token(api)
    for base in (1, 99):
        response = await put_manifest(
            api, admin, base, with_model(NEW_MODEL), project_id="no-such-bot"
        )
        not_found_body(response)
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2


async def test_version_conflict_is_409_before_manifest_validation(api: AsyncClient) -> None:
    admin = await admin_token(api)
    invalid = with_model("mock-gen-small-latest")
    assert_problem(await put_manifest(api, admin, 2, invalid), 409, "MANIFEST_VERSION_CONFLICT")
    assert_problem(await put_manifest(api, admin, 1, invalid), 422, "MANIFEST_INVALID")


async def test_version_conflict_is_409_before_the_equality_check(api: AsyncClient) -> None:
    admin = await admin_token(api)
    for base in (2, 7):
        response = await put_manifest(api, admin, base, DEMO_DOCUMENT)
        assert_problem(response, 409, "MANIFEST_VERSION_CONFLICT")
    assert (await put_manifest(api, admin, 1, DEMO_DOCUMENT)).status_code == 200


# --- Identifiers at their own boundary on the write path --------------------------------


async def test_replace_admits_64_character_identifiers(
    api: AsyncClient,
    backend_settings: Any,  # Any: opaque settings
) -> None:
    await admin_token(api)
    owner = await new_user(api, backend_settings, "owner", "admin")
    await arrange_member_product(
        api, backend_settings, LONGEST, LONGEST, member="owner", member_token=owner
    )
    document = manifest_text(
        client_id=LONGEST, project_id=LONGEST, bindings=[("generation", "mock", NEW_MODEL)]
    )
    response = await put_manifest(api, owner, 1, document, client_id=LONGEST, project_id=LONGEST)
    assert response.status_code == 201, response.text
    assert response.json()["version"] == 2


async def test_replace_with_a_65_character_identifier_is_product_not_found(
    api: AsyncClient,
) -> None:
    admin = await admin_token(api)
    for client_id, project_id in ((TOO_LONG, SUPPORT_BOT), (ACME, TOO_LONG)):
        document = manifest_text(client_id=client_id, project_id=project_id)
        response = await put_manifest(
            api, admin, 1, document, client_id=client_id, project_id=project_id
        )
        not_found_body(response)
    assert (await read_manifest(api, admin))["version"] == 1
    assert (await _accepted(api, admin, 1, with_model(NEW_MODEL)))["version"] == 2
