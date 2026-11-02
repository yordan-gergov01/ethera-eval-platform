"""A Golden: one evaluation case, validated wherever one is written.

Role: `Golden`, the immutable value of one evaluation case (input, expected Decision and the
  rule behind it, failure type, optional context, `expected_numbers`, owner,
  `unfixable_by_code`), its validation (`InvalidGoldenError`), and `count_failure_types`.
Used by: the domain barrel; through it the repositories (rows read back), the services (the
  seed and `publish_dataset_version`) and the API schemas.
Depends on: `evals.evaluation.domain.values`; the standard library.
Key invariants: a Golden is checked on construction, so the seed and every arranged version
  pass the same rules (PP-202, PP-205, INV-EVAL-09): Decision, failure type and owner are
  members of their value sets; `input` and `rule` are not blank; each expected number is a
  decimal string (C-203: kept as written, `"4.90"` stays `"4.90"`); `unfixable_by_code`
  requires an owner other than `engineering`. Failure-type counts always carry all six types,
  zeros included (C-202). Pure.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from evals.evaluation.domain.values import Decision, FailureType, GoldenOwner

DECIMAL_STRING = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


class InvalidGoldenError(ValueError):
    """A Golden breaks one of the domain's rules; the message names the field, never a value."""


@dataclass(frozen=True, slots=True)
class Golden:
    """One evaluation case of a Dataset version (glossary: Golden)."""

    input: str
    expected_decision: Decision
    rule: str
    failure_type: FailureType
    context: str | None = None
    expected_numbers: tuple[str, ...] = ()
    owner: GoldenOwner | None = None
    unfixable_by_code: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.expected_decision, Decision):
            raise InvalidGoldenError("expected_decision is not a Decision")
        if not isinstance(self.failure_type, FailureType):
            raise InvalidGoldenError("failure_type is not a failure type")
        if self.owner is not None and not isinstance(self.owner, GoldenOwner):
            raise InvalidGoldenError("owner is not a Golden owner")
        if not self.input.strip():
            raise InvalidGoldenError("input is blank")
        if not self.rule.strip():
            raise InvalidGoldenError("rule is blank")
        for number in self.expected_numbers:
            if not isinstance(number, str) or DECIMAL_STRING.fullmatch(number) is None:
                raise InvalidGoldenError("expected_numbers holds a value that is not a decimal")
        if self.unfixable_by_code and self.owner in (None, GoldenOwner.ENGINEERING):
            raise InvalidGoldenError("unfixable_by_code requires an owner outside engineering")

    @classmethod
    def of(
        cls,
        *,
        input: str,
        expected_decision: str,
        rule: str,
        failure_type: str,
        context: str | None = None,
        expected_numbers: Iterable[str] = (),
        owner: str | None = None,
        unfixable_by_code: bool = False,
    ) -> "Golden":
        """A Golden from plain values; InvalidGoldenError for any value outside its set."""
        try:
            decision = Decision(expected_decision)
            failure = FailureType(failure_type)
            team = None if owner is None else GoldenOwner(owner)
        except ValueError as exc:
            raise InvalidGoldenError("a value is outside its value set") from exc
        return cls(
            input=input,
            expected_decision=decision,
            rule=rule,
            failure_type=failure,
            context=context,
            expected_numbers=tuple(expected_numbers),
            owner=team,
            unfixable_by_code=unfixable_by_code,
        )


def count_failure_types(counts: Mapping[str, int]) -> dict[FailureType, int]:
    """Counts for every failure type in value-set order, zeros included (C-202)."""
    return {failure_type: counts.get(failure_type.value, 0) for failure_type in FailureType}
