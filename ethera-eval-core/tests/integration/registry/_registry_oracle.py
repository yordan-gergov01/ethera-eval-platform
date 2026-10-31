"""Registry oracle vocabulary: paths, Manifest texts, users and assertions shared by the tests.

Role: the HTTP-level helpers of the sealed oracle for specs/001-product-registry/contract.md —
  building eval.yaml texts, calling the three registry endpoints, reading problem bodies and
  taking before/after snapshots for the "a refusal changes nothing" clauses (§4).
Used by: every test module in tests/integration/registry/.
Depends on: tests/integration/conftest.py (`create_user`, `token_for`, `bearer`,
  `assert_problem`, `ADMIN_PASSWORD`); _contract_fixtures.py for the §6 helpers.
Key invariants: everything goes through public surfaces (the ASGI client, the §6 helpers); the
  Manifest builder writes values verbatim, so a caller can plant any YAML token; `DEMO_DOCUMENT`
  is the §3.1 text copied from the contract, never from the implementation.
"""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from httpx import AsyncClient, Response

from tests.integration.conftest import (
    ADMIN_PASSWORD,
    assert_problem,
    bearer,
    create_user,
    token_for,
)
from tests.integration.registry._contract_fixtures import (
    arrange_client,
    arrange_membership,
    arrange_product,
    demo_document,
    read_audit_rows,
)

Settings = Any  # the test's `backend_settings`, opaque: the oracle imports nothing from backend.*

PRODUCTS = "/api/v1/products"
ME = "/api/v1/users/me"
USER_PASSWORD = "test-only-registry-user-password"
ACME = "acme"
SUPPORT_BOT = "support-bot"
SEED_MODEL = "mock-gen-small-v1"
LONGEST = "a" + "b0-" * 20 + "xyz"  # 64 characters: the identifier pattern's upper bound
TOO_LONG = LONGEST + "z"  # 65 characters

DEMO_DOCUMENT = """product:
  client_id: acme
  project_id: support-bot
bindings:
  - role: generation
    provider: mock
    model: mock-gen-small-v1
allowed_providers:
  - mock
"""

Binding = tuple[str, str, str]
GENERATION: Binding = ("generation", "mock", SEED_MODEL)


def manifest_text(
    *,
    client_id: str = ACME,
    project_id: str = SUPPORT_BOT,
    bindings: Sequence[Binding] = (GENERATION,),
    allowed: Sequence[str] = ("mock",),
    extra: str = "",
) -> str:
    """An eval.yaml text; every value is written verbatim (so tokens and quotes survive)."""
    lines = ["product:", f"  client_id: {client_id}", f"  project_id: {project_id}"]
    lines.append("bindings:" if bindings else "bindings: []")
    for role, provider, model in bindings:
        lines += [f"  - role: {role}", f"    provider: {provider}", f"    model: {model}"]
    lines.append("allowed_providers:" if allowed else "allowed_providers: []")
    lines += [f"  - {provider}" for provider in allowed]
    return "\n".join(lines) + "\n" + extra


def with_model(model: str) -> str:
    """The demo Manifest with another generation model (a real change when it differs)."""
    return manifest_text(bindings=[("generation", "mock", model)])


def product_path(client_id: str = ACME, project_id: str = SUPPORT_BOT) -> str:
    return f"{PRODUCTS}/{client_id}/{project_id}"


def manifest_path(client_id: str = ACME, project_id: str = SUPPORT_BOT) -> str:
    return f"{product_path(client_id, project_id)}/manifest"


async def admin_token(api: AsyncClient) -> str:
    """The seeded administrator's token; the first platform call of most tests."""
    return await token_for(api, "admin", ADMIN_PASSWORD)


async def new_user(api: AsyncClient, settings: Settings, username: str, role: str) -> str:
    """A fresh account with the given role, logged in; returns its token."""
    await create_user(settings, username=username, password=USER_PASSWORD, role=role)
    return await token_for(api, username, USER_PASSWORD)


async def user_id(api: AsyncClient, token: str) -> str:
    response = await api.get(ME, headers=bearer(token))
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


async def put_manifest(
    api: AsyncClient,
    token: str | None,
    base_version: int,
    document: str,
    *,
    client_id: str = ACME,
    project_id: str = SUPPORT_BOT,
) -> Response:
    headers = bearer(token) if token is not None else {}
    return await api.put(
        manifest_path(client_id, project_id),
        json={"base_version": base_version, "document": document},
        headers=headers,
    )


async def read_manifest(
    api: AsyncClient, token: str, client_id: str = ACME, project_id: str = SUPPORT_BOT
) -> dict[str, Any]:
    """The current Manifest as the caller sees it; asserts the 200."""
    response = await api.get(product_path(client_id, project_id), headers=bearer(token))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert (body["client_id"], body["project_id"]) == (client_id, project_id)
    manifest: dict[str, Any] = body["manifest"]
    return manifest


async def list_products(api: AsyncClient, token: str, query: str = "") -> dict[str, Any]:
    response = await api.get(f"{PRODUCTS}{query}", headers=bearer(token))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def listed_ids(listing: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["client_id"], item["project_id"]) for item in listing["items"]]


def assert_offset_timestamp(value: str) -> None:
    """ISO 8601 with a UTC offset (contract §2)."""
    assert datetime.fromisoformat(value).utcoffset() is not None, value


def not_found_body(response: Response) -> dict[str, Any]:
    """A PRODUCT_NOT_FOUND problem without its per-request fields."""
    body = assert_problem(response, 404, "PRODUCT_NOT_FOUND")
    for key in ("status", "code", "detail", "instance", "request_id"):
        assert key in body, body
    return {k: v for k, v in body.items() if k not in ("instance", "request_id")}


def manifest_errors(response: Response) -> list[tuple[str, str]]:
    """The (field, type) pairs of a MANIFEST_INVALID refusal, in response order."""
    body = assert_problem(response, 422, "MANIFEST_INVALID")
    errors = body["errors"]
    assert isinstance(errors, list), body
    pairs: list[tuple[str, str]] = []
    for error in errors:
        assert isinstance(error["field"], str), error
        assert isinstance(error["type"], str), error
        assert isinstance(error["message"], str), error
        pairs.append((error["field"], error["type"]))
    assert len(pairs) == len(set(pairs)), f"a (field, type) pair repeats: {pairs}"
    return pairs


def validation_fields(response: Response) -> set[str]:
    """The `errors[].field` values of a VALIDATION_FAILED refusal."""
    body = assert_problem(response, 422, "VALIDATION_FAILED")
    return {str(error["field"]) for error in body["errors"]}


async def arrange_member_product(
    api: AsyncClient,
    settings: Settings,
    client_id: str,
    project_id: str,
    *,
    member: str,
    member_token: str,
    new_client: bool = True,
) -> str:
    """Client (optional), Product v1 by `admin` and a membership — then checked through the API.

    Returns the document the Product was created from.
    """
    if new_client:
        await arrange_client(settings, client_id)
    document = demo_document(client_id, project_id)
    await arrange_product(settings, client_id, project_id, document, "admin")
    await arrange_membership(settings, member, client_id)
    manifest = await read_manifest(api, member_token, client_id, project_id)
    assert manifest["version"] == 1
    assert manifest["document"] == document
    assert manifest["created_by"] == "admin"
    return document


async def audit_rows_for(settings: Settings, entity_id: str) -> list[Any]:
    return [row for row in await read_audit_rows(settings) if str(row.entity_id) == entity_id]


async def snapshot(
    api: AsyncClient, settings: Settings, tokens: Sequence[str], products: Sequence[str]
) -> dict[str, Any]:
    """Every answer a refusal must leave unchanged (§4): list and detail per user, audit rows."""
    answers: dict[str, Any] = {}
    for index, token in enumerate(tokens):
        listing = await api.get(PRODUCTS, headers=bearer(token))
        answers[f"list-{index}"] = (listing.status_code, _stable(listing))
        for path in products:
            detail = await api.get(path, headers=bearer(token))
            answers[f"get-{index}-{path}"] = (detail.status_code, _stable(detail))
    rows = await read_audit_rows(settings)
    answers["audit"] = sorted(json.dumps(_row_view(row), sort_keys=True) for row in rows)
    return answers


def _stable(response: Response) -> Any:  # Any: a JSON value
    """The body without the per-request fields of a problem (`instance`, `request_id`)."""
    body = response.json()
    if response.status_code >= 400 and isinstance(body, dict):
        return {k: v for k, v in body.items() if k not in ("instance", "request_id")}
    return body


def _row_view(row: Any) -> dict[str, Any]:  # Any: AuditRowView, implementer-typed
    return {
        "action": str(row.action),
        "actor_id": str(row.actor_id),
        "entity_type": str(row.entity_type),
        "entity_id": str(row.entity_id),
        "details": row.details,
        "client_ip": None if row.client_ip is None else str(row.client_ip),
        "created_at": str(row.created_at),
    }


async def assert_seeded_state(api: AsyncClient, token: str, settings: Settings) -> None:
    """The anchor before a no-op check: v1 with the demo Manifest and its one audit row."""
    manifest = await read_manifest(api, token)
    assert manifest["version"] == 1
    assert manifest["bindings"] == [{"role": "generation", "provider": "mock", "model": SEED_MODEL}]
    rows = await read_audit_rows(settings)
    assert [row.action for row in rows if row.entity_type == "product"] == ["manifest_created"]
