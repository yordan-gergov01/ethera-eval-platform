"""The identifier pattern of `client_id` and `project_id` at its own boundaries.

Role: pins evals.registry.domain.identifiers `is_identifier` (contract §2, C-1).
Used by: pytest (unit).
Depends on: nothing beyond the module under test.
Key invariants: 64 characters pass and 65 fail; a trailing newline never passes.
"""

import pytest

from evals.registry.domain.identifiers import is_identifier

LONGEST = "a" + "b0-" * 20 + "xyz"


@pytest.mark.parametrize("value", ["a", "0-9", "a--b", "support-bot", LONGEST])
def test_is_identifier_slug_accepted(value: str) -> None:
    assert is_identifier(value)


@pytest.mark.parametrize(
    "value", ["", "Acme", "-a", "a-", "a_b", "a b", LONGEST + "z", "acme\n", "ä"]
)
def test_is_identifier_other_text_refused(value: str) -> None:
    assert not is_identifier(value)
