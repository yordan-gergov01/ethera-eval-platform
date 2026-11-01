"""The registry's response bodies publish the domain's value sets as enums in the OpenAPI document.

Role: pins evals.registry.api.schemas as published by `evals.app.create_app`: a Model Binding's
  `role` is the `BindingRole` enum and its `provider`, like every entry of `allowed_providers`, is
  an enum equal to the known providers of `FULL_MODEL_ID_RULES`. The web's label maps are keyed on
  the types generated from this document, so a value without a label fails its type check.
Used by: pytest (unit; no database).
Depends on: `evals.app.create_app` with fake settings; `evals.registry.domain` (`BindingRole`)
  and `evals.registry.domain.providers` (`FULL_MODEL_ID_RULES`).
Key invariants: `test_registry_response_value_sets_match_the_domain` compares the published enums
  with the domain's own value sets, so a provider or role added to the domain alone, or typed as a
  plain string again, fails here.
"""

from typing import Any

from backend import BackendSettings
from evals.app import create_app
from evals.registry.domain import BindingRole
from evals.registry.domain.providers import FULL_MODEL_ID_RULES

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


def _enum(schema: Schema, components: dict[str, Schema]) -> set[str]:
    """The values a property schema admits (`enum`, or `const` for one), following a `$ref`."""
    if "$ref" in schema:
        schema = components[schema["$ref"].rsplit("/", 1)[-1]]
    if "const" in schema:
        return {schema["const"]}
    return set(schema.get("enum", ()))


def test_registry_response_value_sets_match_the_domain() -> None:
    document = create_app(BackendSettings.model_validate(SETTINGS)).openapi()
    components: dict[str, Schema] = document["components"]["schemas"]
    binding = components["ModelBindingResponse"]["properties"]
    allowed = components["ManifestResponse"]["properties"]["allowed_providers"]

    roles = {role.value for role in BindingRole}
    providers = set(FULL_MODEL_ID_RULES)
    assert roles
    assert providers
    assert _enum(binding["role"], components) == roles
    assert _enum(binding["provider"], components) == providers
    assert _enum(allowed["items"], components) == providers
