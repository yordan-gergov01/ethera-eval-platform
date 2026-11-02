"""The demo target's knowledge, as data: help-center documents, synonyms, orders, inventions.

Role: the fictional shoe shop's help center (contract §3.3): the documents `returns`, `refunds`
  and `shipping` with their keywords and facts; the synonym table semantic retrieval adds
  (PP-206 R1); the order fixture the order tool reads (R6); and the facts the small models invent
  when nothing covers a question (R3), plus the one they add to shipping answers (R5).
Used by: `demo_target.behaviour`; tests/unit/demo_target/.
Depends on: the standard library only.
Key invariants: keywords are matched as whole words, so `shipping` never matches "ship" (Golden 7
  retrieves nothing under `keyword`) and `refunds` is found through "damaged" (Golden 16);
  synonyms are phrases, never a bare "back", so semantic retrieval stays a superset of keyword
  retrieval without adding `returns` to refund questions; no document covers payment methods,
  discounts or gift cards (Goldens 8 to 10); the order tool fires for an explicit "order number
  N", "order no. N" or "order #N" with any number of digits, but a bare "order N" needs at least
  three digits, so "I received my order 6 weeks ago" (Golden 3) stays off the tool; all values
  are fictional seed data.
"""

import re
from dataclasses import dataclass

ORDER_TOOL = "tool:orders"


@dataclass(frozen=True, slots=True)
class DocumentFact:
    """One statement of a document, offered when the question shares one of its triggers."""

    statement: str
    triggers: frozenset[str]


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    keywords: frozenset[str]
    facts: tuple[DocumentFact, ...]

    @property
    def text(self) -> str:
        return " ".join(fact.statement for fact in self.facts)


RETURN_WINDOW_DAYS = 30
DEFECT_WINDOW_DAYS = 90

RETURN_WINDOW = DocumentFact(
    "Returns are accepted within 30 days of delivery.",
    frozenset({"return", "returns", "days", "weeks"}),
)
RETURN_SHIPPING_COST = DocumentFact(
    "Return shipping costs 4.90, deducted from the refund.",
    frozenset({"shipping", "cost", "costs", "free", "label"}),
)
RETURN_STEPS = DocumentFact(
    "Start a return from your order page, pack the item and hand the parcel to the courier.",
    frozenset({"how", "process", "steps", "send", "ship"}),
)
DEFECT_REFUND = DocumentFact(
    "Items damaged on arrival or defective within 90 days of delivery are refunded in full.",
    frozenset({"damaged", "defect", "defective", "broken", "sole"}),
)
WORN_REFUND = DocumentFact(
    "Worn items are refunded only when defective.",
    frozenset({"wore", "worn"}),
)
REFUND_TIMING = DocumentFact(
    "Refunds arrive in 5-7 business days.",
    frozenset({"long", "take", "takes", "when"}),
)

DOCUMENTS: tuple[Document, ...] = (
    Document(
        "refunds",
        frozenset({"refund", "refunds", "refunded", "money", "damaged", "defect", "defective"}),
        (DEFECT_REFUND, WORN_REFUND, REFUND_TIMING),
    ),
    Document(
        "returns",
        frozenset({"return", "returns", "returned", "returning"}),
        (RETURN_WINDOW, RETURN_SHIPPING_COST, RETURN_STEPS),
    ),
    Document(
        "shipping",
        frozenset({"shipping", "courier", "tracking", "dispatch"}),
        (
            DocumentFact(
                "Orders leave our warehouse within 2 business days.",
                frozenset({"dispatch", "warehouse", "tracking", "courier"}),
            ),
        ),
    ),
)

# R1: semantic retrieval adds the documents these phrases point to.
SYNONYMS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsend (?:it|them|these|this) back\b"), "returns"),
    (re.compile(r"\bship (?:it|them|my \w+) back\b"), "returns"),
    (re.compile(r"\bmoney back\b"), "refunds"),
)

# R6: the order fixture; any other number is unknown.
ORDERS: dict[str, str] = {"1042": "shipped", "1077": "delivered"}
UNKNOWN_ORDER = "unknown"
# An explicit "order number N", "order no. N" or "order #N" names an order whatever its length;
# a bare "order N" needs three digits, so "my order 6 weeks ago" (Golden 3) is no order number.
ORDER_NUMBER = re.compile(
    r"\border\s+(?:(?:(?:number|no\.?)\s*#?|#)\s*(?P<explicit>\d+)|(?P<bare>\d{3,}))\b"
)


@dataclass(frozen=True, slots=True)
class Invention:
    """R3: what a small model asserts, from no source, about a question nothing covers."""

    statement: str
    triggers: frozenset[str]
    # A return window the model makes up; when set, the question is judged against it.
    window_days: int | None = None


INVENTIONS: tuple[Invention, ...] = (
    Invention("Returns are accepted within 14 days.", frozenset({"back", "return"}), 14),
    Invention(
        "We accept every payment method, crypto included.",
        frozenset({"pay", "payment", "crypto"}),
    ),
    Invention("Students get 10% off every order.", frozenset({"discount", "discounts", "student"})),
    Invention("Gift cards are sold from 10 to 100 USD.", frozenset({"gift", "card", "cards"})),
)
DEFAULT_INVENTION = Invention("Yes, that is possible with every order.", frozenset())

# R5: the fact the small models add to shipping answers.
SHIPPING_EMBELLISHMENT = "Return shipping is free on every order."
