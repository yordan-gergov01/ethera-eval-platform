"""A `{number}` path segment names a version only in its canonical decimal form (C-205).

Role: pins evals.evaluation.domain.version_number `parse_version_number`.
Used by: pytest (unit).
Depends on: `evals.evaluation.domain`.
Key invariants: every form `int()` would accept but the contract refuses is listed, so a parser
  that falls back to `int()` fails here; nothing above nine digits reaches SQL (FIX-004).
"""

import pytest

from evals.evaluation.domain import parse_version_number


@pytest.mark.parametrize(
    ("segment", "number"), [("1", 1), ("2", 2), ("10", 10), ("999999999", 999_999_999)]
)
def test_parse_version_number_canonical_decimal_is_the_number(segment: str, number: int) -> None:
    assert parse_version_number(segment) == number


@pytest.mark.parametrize(
    "segment",
    [
        "0",
        "-1",
        "01",
        "02",
        "+1",
        "1.0",
        "1e0",
        " 1",
        "1 ",
        "1\n",
        "1_0",
        "abc",
        "",
        chr(0xFF11),  # FULLWIDTH DIGIT ONE, which int() accepts
        chr(0x0661),  # ARABIC-INDIC DIGIT ONE, which int() accepts
        "1000000000",
        "99999999999999999999",
    ],
)
def test_parse_version_number_any_other_segment_is_none(segment: str) -> None:
    assert parse_version_number(segment) is None
