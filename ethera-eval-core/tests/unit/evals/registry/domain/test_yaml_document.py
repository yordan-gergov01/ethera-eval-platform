"""Reading eval.yaml text: plain values out, every document-level defect refused alone.

Role: pins evals.registry.domain.yaml_document `read_document` — the YAML 1.1 scalar typing it
  reports (strings versus `NON_STRING`), the depth bound, and each document-level problem
  (`malformed`, `unsupported_syntax`, `duplicate_key` with its path).
Used by: pytest (unit).
Depends on: nothing beyond the module under test; no fixtures or services.
Key invariants: deep or alias-heavy input is refused from the event stream before anything
  is composed, so it costs neither stack nor memory
  (test_read_document_deep_nesting_refused_without_recursion).
"""

import pytest

from evals.registry.domain.problems import ManifestProblem, ProblemType
from evals.registry.domain.yaml_document import NON_STRING, read_document


def problem(document: str) -> tuple[str, ProblemType]:
    result = read_document(document)
    assert isinstance(result, ManifestProblem), result
    return result.field, result.type


def test_read_document_plain_values_keep_order_and_strings() -> None:
    result = read_document("b: [x, 'y']\na:\n  c: 1\n  d: ''\n  e:\n")

    assert result == {"b": ["x", "y"], "a": {"c": NON_STRING, "d": "", "e": NON_STRING}}
    assert isinstance(result, dict)
    assert list(result) == ["b", "a"]
    assert repr(NON_STRING) == "NON_STRING"


@pytest.mark.parametrize(
    "token", ["no", "On", "~", "", "010", "0x1f", "1_000", "1:30", ".inf", "2026-10-30"]
)
def test_read_document_yaml_1_1_typed_scalar_not_a_string(token: str) -> None:
    assert read_document(f"k: {token}\n") == {"k": NON_STRING}


@pytest.mark.parametrize("token", ["tRuE", "y", "n", "1e3", "'no'", '"1"'])
def test_read_document_string_scalar_stays_a_string(token: str) -> None:
    result = read_document(f"k: {token}\n")

    assert isinstance(result, dict)
    assert isinstance(result["k"], str)


@pytest.mark.parametrize(
    "document",
    [
        "k: [unclosed\n",
        "a: 1\n---\nb: 2\n",
        "",
        "# only a comment\n",
        "- a\n- b\n",
        "plain",
        "k: " + "[" * 10 + "x" + "]" * 10 + "\n",
    ],
)
def test_read_document_malformed(document: str) -> None:
    assert problem(document) == ("document", ProblemType.MALFORMED)


def test_read_document_ten_levels_admitted() -> None:
    result = read_document("k: " + "[" * 9 + "x" + "]" * 9 + "\n")

    assert isinstance(result, dict)


def test_read_document_deep_nesting_refused_without_recursion() -> None:
    deep = "k: " + "[" * 5000 + "x" + "]" * 5000 + "\n"

    assert problem(deep) == ("document", ProblemType.MALFORMED)


@pytest.mark.parametrize(
    "document",
    [
        "a: &x 1\n",
        "a: &x 1\nb: *x\n",
        "a: !!str x\n",
        "a: !local x\n",
        "a: ! x\n",
        "a: !!seq [x]\n",
        "a:\n  <<: {b: c}\n",
        "1: x\n",
        "yes: x\n",
        "~: x\n",
        "? [a]\n: b\n",
        "a:\n  - {2026-10-30: x}\n",
    ],
)
def test_read_document_unsupported_syntax(document: str) -> None:
    assert problem(document) == ("document", ProblemType.UNSUPPORTED_SYNTAX)


@pytest.mark.parametrize(
    ("document", "field"),
    [
        ("a: 1\na: 2\n", "a"),
        ("a:\n  b: 1\n  b: 2\n", "a.b"),
        ("a:\n  - {c: 1, c: 2}\n", "a[0].c"),
        ("a:\n  - x\n  - {d: 1}\n  - {e: 1, e: 2}\n", "a[2].e"),
    ],
)
def test_read_document_duplicate_key_at_its_path(document: str, field: str) -> None:
    assert problem(document) == (field, ProblemType.DUPLICATE_KEY)
