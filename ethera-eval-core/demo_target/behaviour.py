"""The demo target's behaviour rules R1 to R6 (PP-206): one question in, one deterministic reply.

Role: `reply(configuration, instructions, question)` — retrieves documents (R1), calls the order
  tool for order questions (R6), decides with the model's arithmetic (R2), answers what nothing
  covers by inventing or escalating (R3, R4), embellishes shipping answers on the small models
  (R5), and computes usage (C-209) and the simulated latency (C-210, R-205). `Decision` is the
  demo target's own copy of the Decision value set (PP-202).
Used by: `demo_target.app`; tests/unit/demo_target/ (the golden samples per instruction set and
  `test_demo_target_decisions_equal_the_evaluation_decision_set`).
Depends on: `demo_target.configuration`, `demo_target.help_center`; the standard library.
Key invariants: pure and deterministic — no clock, no randomness, no I/O, no salted `hash()`;
  `latency_ms` comes from SHA-256 of model and question (R-205) and is never waited; usage
  depends on the question, the instruction set and what was retrieved, never on the model
  (C-209); escalation under R4 follows from the instruction set's TEXT (`ESCALATION_INSTRUCTION`),
  so the `.md` file is what changes the behaviour; return windows are inclusive (30 days is
  within 30 days); an escalation asserts no fact.
"""

import hashlib
import math
import re
from dataclasses import dataclass
from enum import StrEnum

from demo_target.configuration import Configuration, ModelSpec, RetrievalMode
from demo_target.help_center import (
    DEFAULT_INVENTION,
    DEFECT_REFUND,
    DEFECT_WINDOW_DAYS,
    DOCUMENTS,
    INVENTIONS,
    ORDER_NUMBER,
    ORDER_TOOL,
    ORDERS,
    RETURN_STEPS,
    RETURN_WINDOW,
    RETURN_WINDOW_DAYS,
    SHIPPING_EMBELLISHMENT,
    SYNONYMS,
    UNKNOWN_ORDER,
    WORN_REFUND,
    Document,
    DocumentFact,
)


class Decision(StrEnum):
    """The action an answer commits to; equal to the platform's Decision set (PP-202)."""

    APPROVE_RETURN = "approve_return"
    DENY_RETURN = "deny_return"
    EXPLAIN_RETURN = "explain_return"
    APPROVE_REFUND = "approve_refund"
    DENY_REFUND = "deny_refund"
    REPORT_STATUS = "report_status"
    ANSWER_FROM_DOCS = "answer_from_docs"
    ESCALATE = "escalate"


# R4: the instruction that instruction set v2 adds; a model escalates when its instructions say so.
ESCALATION_INSTRUCTION = (
    "If neither the documents nor the tool result cover the question, offer a human."
)

LEADS: dict[Decision, str] = {
    Decision.APPROVE_RETURN: "Yes, you can still return it.",
    Decision.DENY_RETURN: "Sorry, this item can no longer be returned.",
    Decision.EXPLAIN_RETURN: "Here is how to return it.",
    Decision.APPROVE_REFUND: "Yes, you get a full refund.",
    Decision.DENY_REFUND: "Sorry, this item cannot be refunded.",
    Decision.REPORT_STATUS: "Here is what our order system says.",
    Decision.ANSWER_FROM_DOCS: "Here is what I can tell you.",
    Decision.ESCALATE: (
        "I cannot answer that from our help center, so let me connect you with a colleague."
    ),
}

STEPS_MARKERS = frozenset({"how", "process", "steps"})
DEFECT_MARKERS = frozenset({"defect", "defective", "damaged", "broken", "broke"})
DEFECT_PHRASES = ("came off",)
WORN_MARKERS = frozenset({"wore", "worn"})
# R2: a span is digits or a number word up to fifteen; "a week" is one week.
NUMBER_WORDS: dict[str, int] = {
    "a": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
}
SPAN = re.compile(rf"\b(\d+|{'|'.join(NUMBER_WORDS)})\s+(days?|weeks?)\b")
WORD = re.compile(r"[^\W_]+")

OUTPUT_BASE_TOKENS = 32
OUTPUT_TOKENS_PER_SOURCE = 16
TOOL_RESULT_TOKENS = 12


@dataclass(frozen=True, slots=True)
class Fact:
    """A fact the answer asserts and where it came from; `None` is an invented fact (C-208)."""

    source: str | None
    statement: str


@dataclass(frozen=True, slots=True)
class Reply:
    answer: str
    retrieved_doc_ids: tuple[str, ...]
    facts_used: tuple[Fact, ...]
    decision: Decision
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(frozen=True, slots=True)
class _Question:
    text: str
    words: frozenset[str]

    @classmethod
    def of(cls, question: str) -> "_Question":
        text = question.lower()
        return cls(text, frozenset(WORD.findall(text)))

    def mentions(self, markers: frozenset[str]) -> bool:
        return not self.words.isdisjoint(markers)

    def span_days(self, days_per_week: int) -> int | None:
        """R2: the span the question names, in days, counted with the model's week."""
        if "yesterday" in self.words:
            return 1
        match = SPAN.search(self.text)
        if match is None:
            return None
        amount = NUMBER_WORDS.get(match.group(1)) or int(match.group(1))
        return amount * days_per_week if match.group(2).startswith("week") else amount


def reply(configuration: Configuration, instructions: str, question: str) -> Reply:
    """The demo target's deterministic answer to `question` (PP-206)."""
    asked = _Question.of(question)
    documents = retrieve(asked, configuration.retrieval)
    order = _order_number(asked.text)
    sources = tuple(sorted([doc.id for doc in documents] + ([ORDER_TOOL] if order else [])))
    facts: tuple[Fact, ...]
    if order is not None:
        status = ORDERS.get(order, UNKNOWN_ORDER)
        decision = Decision.REPORT_STATUS
        facts = (Fact(ORDER_TOOL, f"Order {order} is {status}."),)
    elif not documents:
        decision, facts = _uncovered(asked, configuration.spec, instructions)
    else:
        decision, facts = _from_documents(asked, configuration.spec, documents)
    tool_tokens = TOOL_RESULT_TOKENS if order else 0
    return Reply(
        answer=" ".join([LEADS[decision], *(fact.statement for fact in facts)]),
        retrieved_doc_ids=sources,
        facts_used=facts,
        decision=decision,
        input_tokens=_tokens(instructions)
        + sum(_tokens(doc.text) for doc in documents)
        + _tokens(question)
        + tool_tokens,
        output_tokens=OUTPUT_BASE_TOKENS + OUTPUT_TOKENS_PER_SOURCE * len(sources),
        latency_ms=latency_ms(configuration, question),
    )


def _order_number(text: str) -> str | None:
    """R6: the order number the question names, explicit or bare (see `ORDER_NUMBER`)."""
    match = ORDER_NUMBER.search(text)
    if match is None:
        return None
    return match.group("explicit") or match.group("bare")


def retrieve(asked: _Question, mode: RetrievalMode) -> tuple[Document, ...]:
    """R1: documents sharing a keyword; `semantic` adds the synonym table's (a superset)."""
    found = {doc.id for doc in DOCUMENTS if asked.mentions(doc.keywords)}
    if mode is RetrievalMode.SEMANTIC:
        found |= {doc_id for pattern, doc_id in SYNONYMS if pattern.search(asked.text)}
    return tuple(doc for doc in DOCUMENTS if doc.id in found)


def _from_documents(
    asked: _Question, spec: ModelSpec, documents: tuple[Document, ...]
) -> tuple[Decision, tuple[Fact, ...]]:
    ids = {doc.id for doc in documents}
    decision, facts = _decide_from_documents(asked, spec, documents, ids)
    if spec.embellishes_shipping and "shipping" in ids:  # R5
        facts = (*facts, Fact(None, SHIPPING_EMBELLISHMENT))
    return decision, facts


def _decide_from_documents(
    asked: _Question, spec: ModelSpec, documents: tuple[Document, ...], ids: set[str]
) -> tuple[Decision, tuple[Fact, ...]]:
    days = asked.span_days(spec.days_per_week)
    defect = asked.mentions(DEFECT_MARKERS) or any(p in asked.text for p in DEFECT_PHRASES)
    if "refunds" in ids and defect:
        within = days is None or days <= DEFECT_WINDOW_DAYS
        decision = Decision.APPROVE_REFUND if within else Decision.DENY_REFUND
        return decision, (Fact("refunds", DEFECT_REFUND.statement),)
    if "refunds" in ids and asked.mentions(WORN_MARKERS):
        return Decision.DENY_REFUND, (Fact("refunds", WORN_REFUND.statement),)
    if "returns" in ids and days is not None:
        return _return_window(days, RETURN_WINDOW_DAYS), (Fact("returns", RETURN_WINDOW.statement),)
    if "returns" in ids and asked.mentions(STEPS_MARKERS):
        return Decision.EXPLAIN_RETURN, (Fact("returns", RETURN_STEPS.statement),)
    return Decision.ANSWER_FROM_DOCS, _matching_facts(asked, documents)


def _matching_facts(asked: _Question, documents: tuple[Document, ...]) -> tuple[Fact, ...]:
    """The retrieved facts the question touches; the first retrieved fact when none does."""
    matching = tuple(
        Fact(doc.id, fact.statement)
        for doc in documents
        for fact in doc.facts
        if _touches(asked, fact)
    )
    first = documents[0]
    return matching or (Fact(first.id, first.facts[0].statement),)


def _touches(asked: _Question, fact: DocumentFact) -> bool:
    return asked.mentions(fact.triggers)


def _uncovered(
    asked: _Question, spec: ModelSpec, instructions: str
) -> tuple[Decision, tuple[Fact, ...]]:
    """R3 and R4: no document and no tool result."""
    if ESCALATION_INSTRUCTION in instructions or spec.offers_human_when_uncovered:
        return Decision.ESCALATE, ()
    invention = next(
        (item for item in INVENTIONS if asked.mentions(item.triggers)), DEFAULT_INVENTION
    )
    facts = (Fact(None, invention.statement),)
    days = asked.span_days(spec.days_per_week)
    if invention.window_days is not None and days is not None:
        return _return_window(days, invention.window_days), facts
    if invention.window_days is not None and asked.mentions(STEPS_MARKERS):
        return Decision.EXPLAIN_RETURN, facts
    return Decision.ANSWER_FROM_DOCS, facts


def _return_window(days: int, window_days: int) -> Decision:
    return Decision.APPROVE_RETURN if days <= window_days else Decision.DENY_RETURN


def _tokens(text: str) -> int:
    """A simulated token count: about four characters a token, at least one."""
    return max(1, math.ceil(len(text) / 4))


def latency_ms(configuration: Configuration, question: str) -> int:
    """R-205: a stable point in the model's latency range, from SHA-256 of model and question."""
    spec = configuration.spec
    digest = hashlib.sha256(f"{configuration.model.value}\n{question}".encode()).digest()
    spread = spec.latency_max_ms - spec.latency_min_ms + 1
    return spec.latency_min_ms + int.from_bytes(digest[:8], "big") % spread
