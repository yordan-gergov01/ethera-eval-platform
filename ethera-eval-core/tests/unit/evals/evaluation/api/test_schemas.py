"""The Dataset response bodies publish the domain's value sets in the OpenAPI document.

Role: pins evals.evaluation.api.schemas as published by `evals.app.create_app`: a Golden's
  `expected_decision`, `failure_type` and `owner` are enums equal to the domain's `Decision`,
  `FailureType` and `GoldenOwner` (owner also admits null), and the summary's
  `failure_type_counts` has exactly one required integer property per failure type (C-202).
  The web's label maps are keyed on the types generated from this document, so a value without
  a label fails its type check.
Used by: pytest (unit; no database).
Depends on: `evals.app.create_app` with fake settings; `evals.evaluation.domain`.
Key invariants: `test_evaluation_response_value_sets_match_the_domain` compares the published
  enums with the domain's own value sets, so a value added to the domain alone, or a field typed
  as a plain string again, fails here.
"""

from typing import Any

from backend import BackendSettings
from evals.app import create_app
from evals.evaluation.domain import Decision, FailureType, GoldenOwner

SETTINGS = {
    "db_name": "unit_tests",
    "db_user": "unit_tests",
    "db_password": "test-only-not-a-secret",
    "db_owner_user": "unit_tests_owner",
    "db_owner_password": "test-only-not-a-secret",
    "jwt_secret": "test-only-not-a-secret-signing-key-32-bytes-long",
    "admin_username": "admin",
    "admin_email": "admin@example.com",
    "admin_password": "test-only-admin-password",
    "rabbitmq_vhost": "unit_tests",
    "rabbitmq_user": "unit_tests",
    "rabbitmq_password": "test-only-not-a-secret",
}

Schema = dict[str, Any]  # Any: JSON Schema values


def _enum(schema: Schema, components: dict[str, Schema]) -> set[str | None]:
    """The values a property admits: its enum (through `$ref`), plus None for a nullable one."""
    values: set[str | None] = set()
    for option in schema.get("anyOf", [schema]):
        if option.get("type") == "null":
            values.add(None)
            continue
        if "$ref" in option:
            option = components[option["$ref"].rsplit("/", 1)[-1]]
        values.update(option.get("enum", ()))
    return values


def test_evaluation_response_value_sets_match_the_domain() -> None:
    document = create_app(BackendSettings.model_validate(SETTINGS)).openapi()
    components: dict[str, Schema] = document["components"]["schemas"]
    golden = components["GoldenResponse"]["properties"]
    counts = components["FailureTypeCountsResponse"]

    assert _enum(golden["expected_decision"], components) == {d.value for d in Decision}
    assert _enum(golden["failure_type"], components) == {f.value for f in FailureType}
    assert _enum(golden["owner"], components) == {o.value for o in GoldenOwner} | {None}
    assert set(counts["properties"]) == {f.value for f in FailureType}
    assert set(counts["required"]) == {f.value for f in FailureType}
    assert all(p["type"] == "integer" for p in counts["properties"].values())


def test_value_set_comparison_detects_a_plain_string() -> None:
    assert _enum({"type": "string"}, {}) == set()
