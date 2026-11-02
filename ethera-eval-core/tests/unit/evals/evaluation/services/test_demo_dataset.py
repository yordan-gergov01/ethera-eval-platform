"""The demo Dataset is the contract's: 19 valid Goldens with the §2.1 failure-type counts.

Role: pins evals.evaluation.services.demo_dataset `DEMO_GOLDENS` against contract §3.5 at the
  level the sealed oracle does not reach without a database: the count, the counts per failure
  type, and the one unfixable Golden with its owner (PP-205).
Used by: pytest (unit).
Depends on: `evals.evaluation.services.demo_dataset`, `evals.evaluation.domain`.
Key invariants: the field-by-field comparison with the contract is the sealed oracle's
  (tests/integration/evaluation/test_dataset_seed.py); this file only fails faster.
"""

from collections import Counter

from evals.evaluation.domain import FailureType, GoldenOwner
from evals.evaluation.services.demo_dataset import DEMO_GOLDENS


def test_demo_goldens_are_the_nineteen_of_the_contract() -> None:
    counts = Counter(golden.failure_type for golden in DEMO_GOLDENS)

    assert len(DEMO_GOLDENS) == 19
    assert counts == {
        FailureType.DATE_MATH: 5,
        FailureType.REFUND_RULES: 4,
        FailureType.INVENTED_FACTS: 2,
        FailureType.OUT_OF_DOCS: 3,
        FailureType.RETRIEVAL_MISS: 2,
        FailureType.ORDER_STATUS_TOOL: 3,
    }


def test_only_the_gift_card_golden_is_unfixable_by_code() -> None:
    unfixable = [(i, g) for i, g in enumerate(DEMO_GOLDENS, start=1) if g.unfixable_by_code]

    assert [i for i, _ in unfixable] == [10]
    assert unfixable[0][1].owner is GoldenOwner.SUPPORT_CONTENT
    assert [g.owner for g in DEMO_GOLDENS if not g.unfixable_by_code] == [None] * 18
