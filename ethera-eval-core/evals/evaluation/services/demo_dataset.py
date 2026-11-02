"""The demo Dataset: version 1 of `acme / support-bot`, the 19 Goldens of contract §3.5.

Role: `DEMO_GOLDENS`, the seeded Goldens in their order (FR-203, PP-211).
Used by: `evals.evaluation.services.seed`.
Depends on: `evals.evaluation.domain` (`Golden` and its value sets).
Key invariants: copied from specs/002-demo-target-and-dataset/contract.md §3.5, em and en dashes
  included; each Golden is validated on import (the module fails to load on a bad one, PP-202).
  Changing a Golden here never changes a published version: the seed is create-only, and a
  changed set would be published only as a new version (INV-EVAL-04). Golden 10 is the one no
  code change can fix: owner `support_content`, `unfixable_by_code` (brief §6.3).
"""

from evals.evaluation.domain import Decision, FailureType, Golden, GoldenOwner

_RETURNS_30 = "Returns within 30 days of delivery — doc returns"
_STEPS = "Return steps — doc returns"
_DEFECT_90 = "Defects within 90 days of delivery: full refund — doc refunds"
_TOOL = "Status from the order tool"


def _golden(
    text: str,
    decision: Decision,
    rule: str,
    failure_type: FailureType,
    numbers: tuple[str, ...] = (),
) -> Golden:
    return Golden(
        input=text,
        expected_decision=decision,
        rule=rule,
        failure_type=failure_type,
        expected_numbers=numbers,
    )


D = Decision
F = FailureType

DEMO_GOLDENS: tuple[Golden, ...] = (
    _golden("I bought these sneakers 5 weeks ago, can I return them?", D.DENY_RETURN, _RETURNS_30, F.DATE_MATH, ("30",)),  # noqa: E501
    _golden("My boots were delivered 40 days ago. Can I still return them?", D.DENY_RETURN, _RETURNS_30, F.DATE_MATH, ("30",)),  # noqa: E501
    _golden("I received my order 6 weeks ago, can I return it?", D.DENY_RETURN, _RETURNS_30, F.DATE_MATH, ("30",)),  # noqa: E501
    _golden("Bought them 10 days ago, can I return them?", D.APPROVE_RETURN, _RETURNS_30, F.DATE_MATH, ("30",)),  # noqa: E501
    _golden("I got these 3 weeks ago, can I send them back?", D.APPROVE_RETURN, _RETURNS_30, F.DATE_MATH, ("30",)),  # noqa: E501
    _golden("How do I send them back?", D.EXPLAIN_RETURN, _STEPS, F.RETRIEVAL_MISS),
    _golden("What's the process to ship my shoes back to you?", D.EXPLAIN_RETURN, _STEPS, F.RETRIEVAL_MISS),  # noqa: E501
    _golden("Can I pay with crypto?", D.ESCALATE, "No document covers payment methods; offer a human", F.OUT_OF_DOCS),  # noqa: E501
    _golden("Do you offer student discounts?", D.ESCALATE, "No document covers discounts; offer a human", F.OUT_OF_DOCS),  # noqa: E501
    Golden(
        input="Do you sell gift cards?",
        expected_decision=D.ANSWER_FROM_DOCS,
        rule="Gift-card policy — document to be written by the support content team",
        failure_type=F.OUT_OF_DOCS,
        owner=GoldenOwner.SUPPORT_CONTENT,
        unfixable_by_code=True,
    ),
    _golden("Where is order 1042?", D.REPORT_STATUS, _TOOL, F.ORDER_STATUS_TOOL),
    _golden("What's the status of order 1077?", D.REPORT_STATUS, _TOOL, F.ORDER_STATUS_TOOL),
    _golden("Where is order 9999?", D.REPORT_STATUS, f"{_TOOL}; unknown orders are reported as unknown", F.ORDER_STATUS_TOOL),  # noqa: E501
    _golden("The sole came off after a week. Can I get a refund?", D.APPROVE_REFUND, _DEFECT_90, F.REFUND_RULES, ("90",)),  # noqa: E501
    _golden("I noticed a defect after 15 weeks. Can I get a refund?", D.DENY_REFUND, _DEFECT_90, F.REFUND_RULES, ("90",)),  # noqa: E501
    _golden("My shoes arrived damaged yesterday, do I get my money back?", D.APPROVE_REFUND, "Damaged on arrival: full refund — doc refunds", F.REFUND_RULES),  # noqa: E501
    _golden("I wore the shoes outside and changed my mind. Can I get a refund?", D.DENY_REFUND, "Worn items are refunded only when defective — doc refunds", F.REFUND_RULES),  # noqa: E501
    _golden("Is return shipping free?", D.ANSWER_FROM_DOCS, "Return shipping costs 4.90, deducted from the refund — doc returns", F.INVENTED_FACTS, ("4.90",)),  # noqa: E501
    _golden("How long does a refund take?", D.ANSWER_FROM_DOCS, "Refunds arrive in 5–7 business days — doc refunds", F.INVENTED_FACTS, ("5", "7")),  # noqa: E501, RUF001
)  # fmt: skip
