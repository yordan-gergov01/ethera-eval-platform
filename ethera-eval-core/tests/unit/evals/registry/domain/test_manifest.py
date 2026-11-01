"""Manifest validation, equality and changed sections: every rule of contract §3.3 in isolation.

Role: pins evals.registry.domain.manifest `check_manifest` (each problem type, each
  dependent-problem rule, determinism), `Manifest` equality (C-4) and `changed_sections`.
Used by: pytest (unit).
Depends on: nothing beyond the module under test; no fixtures or services.
Key invariants: expected problems are compared as exact sets; the valid document is the demo
  Manifest, so a case differs from it only by its planted defect.
"""

import pytest

from evals.registry.domain import (
    BindingRole,
    Manifest,
    ModelBinding,
    changed_sections,
    check_manifest,
)

VALID = (
    "product:\n  client_id: acme\n  project_id: support-bot\n"
    "bindings:\n  - role: generation\n    provider: mock\n    model: mock-gen-small-v1\n"
    "allowed_providers:\n  - mock\n"
)
GEN = ModelBinding("generation", "mock", "mock-gen-small-v1")


def problems(document: str) -> set[tuple[str, str]]:
    result = check_manifest(document, "acme", "support-bot")
    assert isinstance(result, tuple), result
    return {(p.field, p.type.value) for p in result}


def doc(product: str, bindings: str, allowed: str, extra: str = "") -> str:
    return f"product: {product}\nbindings: {bindings}\nallowed_providers: {allowed}\n{extra}"


PRODUCT = "{client_id: acme, project_id: support-bot}"
BINDING = "{role: generation, provider: mock, model: mock-gen-small-v1}"


def test_check_manifest_valid_document_parsed_in_order() -> None:
    judge = "{role: judge, provider: mock, model: mock-judge-small-v2}"
    result = check_manifest(doc(PRODUCT, f"[{judge}, {BINDING}]", "[mock]"), "acme", "support-bot")

    assert result == Manifest(
        "acme",
        "support-bot",
        (ModelBinding("judge", "mock", "mock-judge-small-v2"), GEN),
        ("mock",),
    )
    assert isinstance(result, Manifest)
    assert result.generation_binding == GEN


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("product: [unclosed\n", {("document", "malformed")}),
        (VALID + "extra: &a 1\n", {("document", "unsupported_syntax")}),
        (VALID + "product: x\n", {("product", "duplicate_key")}),
        (
            VALID.replace("product:\n  client_id: acme\n  project_id: support-bot\n", ""),
            {("product", "missing")},
        ),
        (doc("x", BINDING, "[mock]"), {("product", "wrong_type"), ("bindings", "wrong_type")}),
        (doc("{client_id: acme}", f"[{BINDING}]", "[mock]"), {("product.project_id", "missing")}),
        (
            doc("{client_id: acme, project_id: support-bot, name: x}", f"[{BINDING}]", "[mock]"),
            {("product.name", "unknown_key")},
        ),
        (
            doc("{client_id: 1, project_id: support-bot}", f"[{BINDING}]", "[mock]"),
            {("product.client_id", "wrong_type")},
        ),
        (
            doc("{client_id: Acme, project_id: support-bot}", f"[{BINDING}]", "[mock]"),
            {("product.client_id", "invalid_value")},
        ),
        (
            doc("{client_id: globex, project_id: portal}", f"[{BINDING}]", "[mock]"),
            {
                ("product.client_id", "product_mismatch"),
                ("product.project_id", "product_mismatch"),
            },
        ),
        (doc(PRODUCT, "[]", "[mock]"), {("bindings", "generation_required")}),
        (doc(PRODUCT, "[x]", "[mock]"), {("bindings[0]", "wrong_type")}),
        (
            doc(PRODUCT, "[{provider: mock, model: mock-a-b-v1}]", "[mock]"),
            {("bindings[0].role", "missing")},
        ),
        (
            doc(PRODUCT, "[{role: critic, provider: mock, model: mock-a-b-v1}]", "[mock]"),
            {("bindings[0].role", "invalid_value")},
        ),
        (
            doc(PRODUCT, f"[{BINDING}, {BINDING}]", "[mock]"),
            {("bindings[1].role", "duplicate_role")},
        ),
        (
            doc(
                PRODUCT, "[{role: generation, provider: mock, model: mock-a-b-v1, t: 1}]", "[mock]"
            ),
            {("bindings[0].t", "unknown_key")},
        ),
        (
            doc(PRODUCT, "[{role: generation, provider: mock, model: mock-a-b-v0}]", "[mock]"),
            {("bindings[0].model", "alias")},
        ),
        (
            doc(PRODUCT, "[{role: generation, provider: mock, model: ''}]", "[mock]"),
            {("bindings[0].model", "invalid_value")},
        ),
        (
            doc(PRODUCT, "[{role: generation, provider: mock, model: 7}]", "[mock]"),
            {("bindings[0].model", "wrong_type")},
        ),
        (
            doc(PRODUCT, "[{role: generation, provider: x, model: gpt}]", "[mock]"),
            {
                ("bindings[0].provider", "unknown_provider"),
                ("bindings[0].provider", "provider_not_allowed"),
            },
        ),
        (
            doc(PRODUCT, "[{role: generation, provider: 1, model: m}]", "[mock]"),
            {("bindings[0].provider", "wrong_type")},
        ),
        (
            doc(PRODUCT, "[{role: generation, model: m}]", "[mock]"),
            {("bindings[0].provider", "missing")},
        ),
        (doc(PRODUCT, f"[{BINDING}]", "[]"), {("allowed_providers", "invalid_value")}),
        (doc(PRODUCT, f"[{BINDING}]", "mock"), {("allowed_providers", "wrong_type")}),
        (doc(PRODUCT, f"[{BINDING}]", "[mock, 1]"), {("allowed_providers[1]", "wrong_type")}),
        (doc(PRODUCT, f"[{BINDING}]", "[mock, x]"), {("allowed_providers[1]", "unknown_provider")}),
        (
            doc(PRODUCT, f"[{BINDING}]", "[mock, mock]"),
            {("allowed_providers[1]", "duplicate_value")},
        ),
        (
            doc(PRODUCT, f"[{BINDING}]", "[x]"),
            {
                ("allowed_providers[0]", "unknown_provider"),
                ("bindings[0].provider", "provider_not_allowed"),
            },
        ),
        (doc(PRODUCT, f"[{BINDING}]", "[mock]", "owner: x\n"), {("owner", "unknown_key")}),
        ("product: " + PRODUCT + "\n", {("bindings", "missing"), ("allowed_providers", "missing")}),
    ],
)
def test_check_manifest_reports_exactly_its_problems(
    document: str, expected: set[tuple[str, str]]
) -> None:
    assert problems(document) == expected


def test_duplicate_unknown_provider_reports_both_problems() -> None:
    # A repeated unknown provider is unknown at every position AND a duplicate (independent
    # causes, FR-004): neither problem hides the other.
    document = doc(PRODUCT, f"[{BINDING}]", "[foo, foo]")

    assert problems(document) == {
        ("allowed_providers[0]", "unknown_provider"),
        ("allowed_providers[1]", "unknown_provider"),
        ("allowed_providers[1]", "duplicate_value"),
        ("bindings[0].provider", "provider_not_allowed"),
    }


def test_check_manifest_same_document_same_problems_same_order() -> None:
    document = doc(
        PRODUCT, "[{role: generation, provider: mock, model: m}]", "[mock, mock]", "o: 1\n"
    )

    first = check_manifest(document, "acme", "support-bot")
    second = check_manifest(document, "acme", "support-bot")

    assert first == second
    assert isinstance(first, tuple)
    assert len(first) == 3
    assert all(problem.message and "mock" not in problem.message for problem in first)


def test_manifest_equality_ignores_text_and_keeps_binding_order() -> None:
    reformatted = "# comment\n" + doc(PRODUCT, f"[{BINDING}]", "['mock']")
    judge = "{role: judge, provider: mock, model: mock-judge-small-v1}"

    assert check_manifest(VALID, "acme", "support-bot") == check_manifest(
        reformatted, "acme", "support-bot"
    )
    assert check_manifest(
        doc(PRODUCT, f"[{BINDING}, {judge}]", "[mock]"), "acme", "support-bot"
    ) != check_manifest(doc(PRODUCT, f"[{judge}, {BINDING}]", "[mock]"), "acme", "support-bot")


def test_changed_sections_names_each_differing_section_sorted() -> None:
    before = Manifest("acme", "support-bot", (GEN,), ("mock",))
    other_binding = ModelBinding(BindingRole.GENERATION, "mock", "mock-gen-large-v2")

    assert changed_sections(before, before) == ()
    assert changed_sections(
        before, Manifest("acme", "support-bot", (other_binding,), ("mock",))
    ) == ("bindings",)
    everything = Manifest("globex", "portal", (other_binding,), ("mock", "other"))
    assert changed_sections(before, everything) == ("allowed_providers", "bindings", "product")
