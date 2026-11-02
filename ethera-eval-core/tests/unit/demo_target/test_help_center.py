"""The demo target's help-center data keeps the traps the scenario matrix rests on.

Role: pins demo_target.help_center: a bare order number needs three or more digits (Golden 3's
  "my order 6 weeks ago" calls no tool, R6 still fires on "order 1042"); no document covers
  payment methods, discounts or gift cards (Goldens 8 to 10); the `shipping` keywords never hold
  "ship" (Golden 7 retrieves nothing under `keyword`); every synonym is a phrase, never a bare
  word (semantic retrieval adds `returns` only to return questions, R1); the order fixture.
Used by: pytest (unit; no services).
Depends on: `demo_target.help_center`.
Key invariants: these are data checks with clearer failures than a matrix cell; the matrix
  itself is sealed in tests/integration/evaluation/test_scenario_matrix.py.
"""

from demo_target.help_center import DOCUMENTS, ORDER_NUMBER, ORDERS, SYNONYMS


def test_a_bare_order_number_needs_three_digits() -> None:
    assert ORDER_NUMBER.search("i received my order 6 weeks ago") is None
    assert ORDER_NUMBER.search("i received my order 42 days ago") is None
    match = ORDER_NUMBER.search("where is order 1042?")
    assert match is not None
    assert match.group("bare") == "1042"


def test_documents_never_cover_payments_discounts_or_gift_cards() -> None:
    uncovered = {"pay", "payment", "crypto", "discount", "discounts", "student", "gift", "card"}
    for document in DOCUMENTS:
        assert document.keywords.isdisjoint(uncovered), document.id


def test_documents_are_the_contract_three_and_shipping_never_matches_ship() -> None:
    by_id = {document.id: document for document in DOCUMENTS}
    assert set(by_id) == {"returns", "refunds", "shipping"}
    assert "ship" not in by_id["shipping"].keywords


def test_synonyms_are_phrases_pointing_at_documents() -> None:
    ids = {document.id for document in DOCUMENTS}
    for pattern, doc_id in SYNONYMS:
        assert " " in pattern.pattern, pattern.pattern
        assert doc_id in ids
        assert pattern.search("back") is None


def test_orders_fixture_holds_the_contract_statuses() -> None:
    assert ORDERS == {"1042": "shipped", "1077": "delivered"}
