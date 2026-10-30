# Evaluation guideline — acme / support-bot

The most important evaluation artifact (brief §4, "AI Engineering" ch. 4): what the product
must do and must not do, the criteria, a scoring rule per criterion, a rubric with examples,
and a usefulness threshold tied to a business outcome. Status per item: **accepted** (brief)
or **proposed** (awaiting the owner at the slice that first uses it).

## The product

A fictional footwear store's customer-support assistant that answers from a small set of
help-center documents and can look up order status through a tool (accepted, brief §6).

## Must do (accepted)

- Apply the store's policies correctly, including date arithmetic (e.g. a 30-day return
  window: "5 weeks ago" is outside it).
- Answer only from the retrieved help-center documents and tool results.
- Find the relevant document even when the customer's words differ from the document's
  ("send them back" → return policy).
- Report order status through the tool, not from memory.
- Apply refund rules exactly.

## Must not do (accepted)

- Invent facts, policies, dates or amounts not in the documents or tool results.
- Answer questions the documents do not cover as if they did.
- Leave the customer without a path when it cannot answer — it offers a human instead.

## Failure types and their Metrics

| Failure type | Metric | Evidence it receives (only) | Pass when | Status |
|---|---|---|---|---|
| `date_math` / `refund_rules` (policy) | `policy_correct` | `decision`, numbers in the answer, expected decision + rule, full policy context | decision equals the expected decision and every number the rule implies matches | accepted (metric); threshold proposed: exact match |
| `invented_facts` | `stays_in_docs` | `facts_used`, `retrieved_doc_ids` | `facts_used ⊆ retrieved documents` | accepted (metric); threshold proposed: no fact outside |
| `out_of_docs` | `offers_human_when_unknown` | `decision`, `retrieved_doc_ids`, the Golden's expected decision | when the expected decision is "escalate", the answer offers a human and asserts no policy | accepted (metric); rule proposed |
| (all) | `answer_relevancy` | `answer`, Golden `input` | lexical overlap of key terms ≥ threshold | accepted (metric); threshold proposed: 0.3 |
| `order_status_tool` | `policy_correct` with tool context | `decision`, tool result | decision matches the tool's status | proposed (mapping) |

Each Metric reads only its declared fields; a test proves it (see `add-metric` skill).

## Scoring

- Per Trial, per Metric: pass / fail with a reason (accepted: every verdict has a reason).
- A Trial passes iff every applicable Metric passes (proposed, INV-EVAL-08).
- Per Golden across N = 3 Trials: always pass / always fail / flaky / error (accepted).
- Cheap deterministic checks on everything; the expensive judge only on samples — in the PoC
  every judge is a deterministic mock, so everything is checked (accepted, recorded as the
  PoC simplification).
- Results are sliced by failure type, so aggregates cannot hide a regression (Simpson's
  paradox) (accepted).

## Rubric examples (proposed; the seed Dataset in slice 002 makes them concrete)

| Golden (abridged) | Expected decision + rule | Passes | Fails |
|---|---|---|---|
| "I bought these 5 weeks ago, can I return them?" | `deny_return` — returns within 30 days of delivery | "Sorry, the 30-day window has passed…" | "Yes, you can return them" (date math) |
| "How do I send them back?" | `explain_return` — return policy doc | cites the return steps from the return-policy document | "I'm not sure" when the doc exists (retrieval miss) |
| "Do you sell gift cards?" (no document exists) | `escalate` — out of docs; owner: support content team | offers a human, asserts nothing | invents a gift-card policy |
| "Where is order 1042?" | `report_status` — order tool | states the tool's status | states a status the tool did not return |

## Usefulness threshold (proposed)

The assistant is useful when **all `policy_correct` Goldens are always pass and no Golden is
always fail on `stays_in_docs`** — business outcome: no customer is told a wrong refund or
return answer, which is the cost driver for the store's support team. Owner to confirm at
slice 002/004.

## Judge consistency

The judge is fixed across runs that are compared (accepted, INV-CMP-02). Its consistency is
measured by the judge-flaky classification (identical outputs, different verdicts). The demo's
seeded `NoisyJudge` on one Metric produces exactly one such Golden (accepted, brief §6.10).
