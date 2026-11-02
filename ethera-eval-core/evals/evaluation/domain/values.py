"""The value sets a Golden is written in: Decision, failure type and Golden owner.

Role: `Decision` (PP-202), `FailureType` (PP-203) and `GoldenOwner` (PP-205), the closed value
  sets of `docs/domain/glossary.md`, as StrEnums.
Used by: `evals.evaluation.domain.golden`, the domain barrel; through it the repositories, the
  services (the demo Dataset) and `evals.evaluation.api.schemas`, which publishes them as enums
  in the OpenAPI document (`test_evaluation_response_value_sets_match_the_domain`).
Depends on: the standard library only.
Key invariants: values are part of the API and of stored rows: never rename one. The Decision
  set is global for the PoC; the demo target keeps its own copy (it imports nothing) and
  `test_demo_target_decisions_equal_the_evaluation_decision_set` proves the two equal. Pure.
"""

from enum import StrEnum


class Decision(StrEnum):
    """The action a Product's answer commits to (glossary: Decision)."""

    APPROVE_RETURN = "approve_return"
    DENY_RETURN = "deny_return"
    EXPLAIN_RETURN = "explain_return"
    APPROVE_REFUND = "approve_refund"
    DENY_REFUND = "deny_refund"
    REPORT_STATUS = "report_status"
    ANSWER_FROM_DOCS = "answer_from_docs"
    ESCALATE = "escalate"


class FailureType(StrEnum):
    """What kind of mistake a Golden catches; each has its Metric (PP-203)."""

    DATE_MATH = "date_math"
    REFUND_RULES = "refund_rules"
    INVENTED_FACTS = "invented_facts"
    OUT_OF_DOCS = "out_of_docs"
    RETRIEVAL_MISS = "retrieval_miss"
    ORDER_STATUS_TOOL = "order_status_tool"


class GoldenOwner(StrEnum):
    """The team that owns a Golden's fix (PP-205): a team, never a person."""

    ENGINEERING = "engineering"
    SUPPORT_CONTENT = "support_content"
