"""A Golden is validated wherever one is written: value sets, blanks, numbers, owners.

Role: pins evals.evaluation.domain.golden — `Golden` construction (PP-202, PP-205, C-203),
  `Golden.of` from plain values, and `count_failure_types` (C-202).
Used by: pytest (unit).
Depends on: `evals.evaluation.domain`.
Key invariants: every rule has a case that breaks it and one that passes; the oracle's own
  defaults (a plain rule, no context, no numbers, no owner) must be accepted.
"""

from typing import Any

import pytest

from evals.evaluation.domain import (
    Decision,
    FailureType,
    Golden,
    GoldenOwner,
    InvalidGoldenError,
    count_failure_types,
)

PLAIN: dict[str, Any] = {  # Any: keyword values of every type, refused ones included
    "input": "Can I return them?",
    "expected_decision": "deny_return",
    "rule": "An arranged rule",
    "failure_type": "date_math",
}


def test_of_plain_values_builds_the_typed_golden() -> None:
    golden = Golden.of(
        **PLAIN,
        context="Order 1042",
        expected_numbers=["4.90", "90", "-3"],
        owner="support_content",
        unfixable_by_code=True,
    )

    assert golden.expected_decision is Decision.DENY_RETURN
    assert golden.failure_type is FailureType.DATE_MATH
    assert golden.owner is GoldenOwner.SUPPORT_CONTENT
    assert golden.expected_numbers == ("4.90", "90", "-3")


def test_of_defaults_are_accepted() -> None:
    golden = Golden.of(**PLAIN)

    assert (golden.context, golden.expected_numbers, golden.owner) == (None, (), None)
    assert golden.unfixable_by_code is False


@pytest.mark.parametrize(
    "field", ["expected_decision", "failure_type", "owner"], ids=lambda f: f"bad_{f}"
)
def test_of_value_outside_its_set_is_refused(field: str) -> None:
    with pytest.raises(InvalidGoldenError):
        Golden.of(**{**PLAIN, field: "Deny_Return"})


@pytest.mark.parametrize("field", ["input", "rule"])
def test_blank_text_is_refused(field: str) -> None:
    with pytest.raises(InvalidGoldenError, match=field):
        Golden.of(**{**PLAIN, field: "  "})


@pytest.mark.parametrize(
    "number", ["4,90", "1e3", "", " 30", "30.", ".5", "+1", chr(0xFF13) + chr(0xFF10)]
)
def test_expected_number_that_is_not_a_decimal_string_is_refused(number: str) -> None:
    with pytest.raises(InvalidGoldenError, match="expected_numbers"):
        Golden.of(**PLAIN, expected_numbers=[number])


def test_expected_number_that_is_not_a_string_is_refused() -> None:
    with pytest.raises(InvalidGoldenError, match="expected_numbers"):
        Golden(
            input="q",
            expected_decision=Decision.ESCALATE,
            rule="r",
            failure_type=FailureType.OUT_OF_DOCS,
            expected_numbers=(30,),  # type: ignore[arg-type]  # the refused case itself
        )


@pytest.mark.parametrize("owner", [None, "engineering"])
def test_unfixable_by_code_without_an_owner_outside_engineering_is_refused(
    owner: str | None,
) -> None:
    with pytest.raises(InvalidGoldenError, match="unfixable_by_code"):
        Golden.of(**PLAIN, owner=owner, unfixable_by_code=True)


def test_engineering_owner_of_a_fixable_golden_is_accepted() -> None:
    assert Golden.of(**PLAIN, owner="engineering").owner is GoldenOwner.ENGINEERING


@pytest.mark.parametrize(
    ("field", "value"),
    [("expected_decision", "deny_return"), ("failure_type", "date_math"), ("owner", "engineering")],
)
def test_untyped_value_passed_directly_is_refused(field: str, value: str) -> None:
    typed = {
        "input": "q",
        "expected_decision": Decision.DENY_RETURN,
        "rule": "r",
        "failure_type": FailureType.DATE_MATH,
    }
    with pytest.raises(InvalidGoldenError):
        Golden(**{**typed, field: value})  # type: ignore[arg-type]  # the refused case itself


def test_count_failure_types_has_every_type_with_zeros() -> None:
    counts = count_failure_types({"refund_rules": 2, "out_of_docs": 1})

    assert list(counts) == list(FailureType)
    assert counts[FailureType.REFUND_RULES] == 2
    assert counts[FailureType.OUT_OF_DOCS] == 1
    assert sum(counts.values()) == 3
