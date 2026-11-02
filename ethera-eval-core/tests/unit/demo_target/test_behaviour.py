"""The demo target's behaviour rules, its Decision set, usage and simulated latency.

Role: pins demo_target.behaviour beyond the sealed matrix: the Decision set equals the
  platform's (PP-202, `test_demo_target_decisions_equal_the_evaluation_decision_set`); R1 keeps
  semantic retrieval a superset of keyword retrieval; R2 counts weeks with the model's week; the
  return window is inclusive; R3 invents a 14-day window for return questions nothing covers;
  usage is independent of the model (C-209); latency comes from SHA-256 of model and question
  (R-205) and stays inside the model's range; order questions call the order tool whatever
  the wording (`test_order_questions_call_the_order_tool_whatever_the_wording`); spans in number
  words count like digits (`test_spans_in_number_words_count_like_digits`).
Used by: pytest (unit; no services).
Depends on: `demo_target.behaviour`, `demo_target.configuration`, `demo_target.help_center`;
  `evals.evaluation.domain` (`Decision`) — a test may import both (PP-202).
Key invariants: the expected latency is recomputed here from `hashlib`, never from Python's
  salted `hash()`, so a switch to `hash()` fails across processes and here.
"""

import hashlib

import pytest

from demo_target.behaviour import Decision, latency_ms, reply
from demo_target.configuration import MODELS, Configuration, Model, read_instruction_set
from evals.evaluation.domain import Decision as PlatformDecision

QUESTIONS = (
    "I got these 3 weeks ago, can I send them back?",
    "My shoes arrived damaged yesterday, do I get my money back?",
    "Is return shipping free?",
    "Where is order 1042?",
    "Do you sell gift cards?",
)


def test_demo_target_decisions_equal_the_evaluation_decision_set() -> None:
    assert {d.value for d in Decision} == {d.value for d in PlatformDecision}


@pytest.mark.parametrize("question", QUESTIONS)
def test_reply_semantic_retrieval_is_a_superset_of_keyword(question: str) -> None:
    keyword = Configuration.of("mock-gen-small-v1", "v1", "keyword")
    semantic = Configuration.of("mock-gen-small-v1", "v1", "semantic")
    instructions = read_instruction_set(keyword.instruction_set)
    found = set(reply(keyword, instructions, question).retrieved_doc_ids)
    assert found <= set(reply(semantic, instructions, question).retrieved_doc_ids)


@pytest.mark.parametrize(
    ("model", "question", "expected"),
    [
        ("mock-gen-small-v1", "I got them 6 weeks ago, can I return them?", "approve_return"),
        ("mock-gen-small-v2", "I got them 6 weeks ago, can I return them?", "deny_return"),
        ("mock-gen-medium-v1", "I got them 30 days ago, can I return them?", "approve_return"),
        ("mock-gen-medium-v1", "I got them 31 days ago, can I return them?", "deny_return"),
        ("mock-gen-small-v2", "The sole came off after one week. Refund?", "approve_refund"),
    ],
)
def test_reply_counts_weeks_with_the_models_week_and_inclusive_windows(
    model: str, question: str, expected: str
) -> None:
    configuration = Configuration.of(model, "v1", "keyword")
    answered = reply(configuration, read_instruction_set(configuration.instruction_set), question)
    assert answered.decision == expected


def test_reply_uncovered_return_question_invents_a_fourteen_day_window() -> None:
    configuration = Configuration.of("mock-gen-small-v1", "v1", "keyword")
    instructions = read_instruction_set(configuration.instruction_set)
    within = reply(configuration, instructions, "I got these 2 weeks ago, can I send them back?")
    beyond = reply(configuration, instructions, "I got these 3 weeks ago, can I send them back?")
    assert (within.decision, beyond.decision) == ("approve_return", "deny_return")
    assert [fact.source for fact in within.facts_used] == [None]


def test_reply_uncovered_question_without_a_known_topic_invents_a_default_fact() -> None:
    configuration = Configuration.of("mock-gen-small-v2", "v1", "keyword")
    answered = reply(configuration, read_instruction_set(configuration.instruction_set), "?")
    assert answered.decision == "answer_from_docs"
    assert [fact.source for fact in answered.facts_used] == [None]


@pytest.mark.parametrize("question", QUESTIONS)
def test_reply_usage_does_not_depend_on_the_model(question: str) -> None:
    usages = set()
    for model in Model:
        configuration = Configuration.of(model.value, "v1", "semantic")
        answered = reply(
            configuration, read_instruction_set(configuration.instruction_set), question
        )
        usages.add((answered.input_tokens, answered.output_tokens))
    assert len(usages) == 1


@pytest.mark.parametrize("model", list(Model))
def test_latency_ms_is_the_sha256_point_in_the_models_range(model: Model) -> None:
    configuration = Configuration.of(model.value, "v1", "keyword")
    spec = MODELS[model]
    for question in QUESTIONS:
        digest = hashlib.sha256(f"{model.value}\n{question}".encode()).digest()
        spread = spec.latency_max_ms - spec.latency_min_ms + 1
        expected = spec.latency_min_ms + int.from_bytes(digest[:8], "big") % spread
        assert latency_ms(configuration, question) == expected
        assert spec.latency_min_ms <= expected <= spec.latency_max_ms


ORDER_WORDINGS = (
    ("What's the status of order number 1077?", "1077", "delivered"),
    ("Where is order no. 42?", "42", "unknown"),
    ("Where is order no 7?", "7", "unknown"),
    ("Where is order #5?", "5", "unknown"),
    ("Where is order #1042?", "1042", "shipped"),
    ("Where is order 1042?", "1042", "shipped"),
)


# The five configurations of the scenario matrix (contract §3.4): baseline, prompt, retrieval,
# release and expensive.
CONFIGURATIONS = (
    ("mock-gen-small-v1", "v1", "keyword"),
    ("mock-gen-small-v1", "v2", "keyword"),
    ("mock-gen-small-v1", "v1", "semantic"),
    ("mock-gen-small-v2", "v1", "keyword"),
    ("mock-gen-medium-v1", "v1", "keyword"),
)


@pytest.mark.parametrize(("model", "instruction_set", "retrieval"), CONFIGURATIONS)
@pytest.mark.parametrize(("question", "number", "status"), ORDER_WORDINGS)
def test_order_questions_call_the_order_tool_whatever_the_wording(
    model: str, instruction_set: str, retrieval: str, question: str, number: str, status: str
) -> None:
    configuration = Configuration.of(model, instruction_set, retrieval)
    answered = reply(configuration, read_instruction_set(configuration.instruction_set), question)
    assert answered.decision == "report_status"
    assert "tool:orders" in answered.retrieved_doc_ids
    assert [(fact.source, fact.statement) for fact in answered.facts_used] == [
        ("tool:orders", f"Order {number} is {status}.")
    ]


@pytest.mark.parametrize(
    ("model", "question", "expected"),
    [
        (
            "mock-gen-small-v2",
            "I noticed a defect after fifteen weeks. Can I get a refund?",
            "deny_refund",
        ),
        (
            "mock-gen-medium-v1",
            "I noticed a defect after fifteen weeks. Can I get a refund?",
            "deny_refund",
        ),
        (
            "mock-gen-small-v1",
            "I noticed a defect after fifteen weeks. Can I get a refund?",
            "approve_refund",
        ),
        ("mock-gen-small-v1", "I bought these two weeks ago, can I return them?", "approve_return"),
        ("mock-gen-small-v2", "I bought these two weeks ago, can I return them?", "approve_return"),
        (
            "mock-gen-medium-v1",
            "I bought these two weeks ago, can I return them?",
            "approve_return",
        ),
    ],
)
def test_spans_in_number_words_count_like_digits(model: str, question: str, expected: str) -> None:
    configuration = Configuration.of(model, "v1", "keyword")
    answered = reply(configuration, read_instruction_set(configuration.instruction_set), question)
    assert answered.decision == expected
