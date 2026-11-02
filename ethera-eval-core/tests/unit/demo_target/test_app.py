"""The demo target's HTTP surface: the request log line, refusals and determinism across apps.

Role: pins demo_target.app beyond the sealed oracle: one log line per request with route
  template, status and model only (R-206) — so the sealed never-log test cannot pass
  because nothing is logged (SEALED.md, not sealed #7); 422 bodies that never echo the input;
  oversized bodies refused before parsing; unknown paths logged without the raw path; and
  byte-identical answers from fresh app instances.
Used by: pytest (unit; no services — the app runs in process through httpx's ASGITransport).
Depends on: `demo_target` (barrel), `demo_target.app` (`MAX_BODY_BYTES`, `REFUSAL`), httpx, and
  the §6 helpers `demo_target_client` / `demo_target_logs` in
  tests/integration/evaluation_fixtures.py.
Key invariants: log assertions parse each captured line as JSON and compare it whole, so an
  extra field (a question, an answer, a raw path) fails the test.
"""

import json

from demo_target.app import MAX_BODY_BYTES, REFUSAL
from tests.integration.evaluation_fixtures import demo_target_client, demo_target_logs

SMALL = ("mock-gen-small-v1", "v1", "keyword")
QUESTION = "Bought them 10 days ago, can I return them?"


def _lines(captured: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in captured.splitlines() if line]


async def test_request_log_one_line_per_request_holds_route_status_and_model_only() -> None:
    async with demo_target_logs(*SMALL) as (target, logs):
        answered = await target.post("/chat", json={"question": QUESTION})
        refused = await target.post("/chat", json={"question": QUESTION, "history": []})
        missing = await target.get(f"/chat/{QUESTION}")
        captured = logs()
    assert (answered.status_code, refused.status_code, missing.status_code) == (200, 422, 404)
    model = SMALL[0]
    assert _lines(captured) == [
        {"route": "/chat", "status": 200, "model": model},
        {"route": "/chat", "status": 422, "model": model},
        {"route": "unmatched", "status": 404, "model": model},
    ]
    assert "10 days" not in captured
    assert answered.json()["answer"] not in captured


async def test_request_log_capture_ends_with_its_context() -> None:
    async with demo_target_logs(*SMALL) as (target, logs):
        await target.post("/chat", json={"question": QUESTION})
    async with demo_target_client(*SMALL) as target:
        await target.post("/chat", json={"question": QUESTION})
    assert len(_lines(logs())) == 1


async def test_chat_refusal_body_never_echoes_the_input() -> None:
    marker = "qzrefusalechomarker"
    async with demo_target_client(*SMALL) as target:
        response = await target.post("/chat", json={"question": marker * 200})
    assert response.status_code == 422
    assert response.json() == REFUSAL
    assert marker not in response.text


async def test_chat_oversized_body_is_refused_before_parsing() -> None:
    padding = " " * MAX_BODY_BYTES
    raw = f'{{"question": "{QUESTION}"}}{padding}'.encode()
    async with demo_target_logs(*SMALL) as (target, logs):
        response = await target.post(
            "/chat", content=raw, headers={"content-type": "application/json"}
        )
        just_below = await target.post(
            "/chat",
            content=raw[: MAX_BODY_BYTES - 1],
            headers={"content-type": "application/json"},
        )
        captured = logs()
    assert response.status_code == 422
    assert response.json() == REFUSAL
    assert just_below.status_code == 200, just_below.text
    assert [line["status"] for line in _lines(captured)] == [422, 200]


async def test_chat_fresh_app_instances_answer_byte_identically() -> None:
    bodies = []
    for _ in range(3):
        async with demo_target_client("mock-gen-medium-v1", "v2", "semantic") as target:
            bodies.append((await target.post("/chat", json={"question": QUESTION})).content)
    assert bodies[0] == bodies[1] == bodies[2]
