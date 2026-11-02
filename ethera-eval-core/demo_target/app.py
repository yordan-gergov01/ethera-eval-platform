"""The demo target's HTTP application: `POST /chat` in one start-up configuration (contract §2.3).

Role: `create_app(configuration)` builds the FastAPI app of the client's product: it reads the
  instruction set from its `.md` file (FR-206), answers `/chat` through `demo_target.behaviour`,
  refuses malformed and oversized bodies with 422 (C-206), and logs one line per request.
Used by: the barrel; the §6 helpers `demo_target_client` and `demo_target_logs` in
  tests/integration/evaluation_fixtures.py; tests/unit/demo_target/. Its compose service and
  runtime image arrive with the runner in slice 003 (D-024 Fork D1, dated deviation).
Depends on: FastAPI, Pydantic, Starlette's ASGI types; `demo_target.behaviour`,
  `demo_target.configuration`; stdlib `logging` and `json`. Nothing from this repository's other
  packages (FR-208, import-linter contract).
Key invariants: the request line holds route template, status and model only — never
  the question, the answer or a raw path (C-214, R-206); the 422 body never echoes the input;
  a body larger than `MAX_BODY_BYTES` is refused with the same 422 before it is parsed (it cannot
  hold a valid question: 2,000 code points escaped as `\\uXXXX` pairs stay below the cap); no
  handler is installed here — whoever runs the app attaches one to `LOGGER_NAME`.
"""

import json
import logging
from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from demo_target.behaviour import Decision, reply
from demo_target.configuration import CURRENCY, Configuration, read_instruction_set

LOGGER_NAME = "demo_target"
CHAT_ROUTE = "/chat"
UNMATCHED_ROUTE = "unmatched"
MAX_QUESTION_CHARS = 2000
MAX_BODY_BYTES = 32 * 1024
REFUSAL = {
    "detail": "The body must be a JSON object with exactly one question of 1 to 2000 characters."
}

logger = logging.getLogger(LOGGER_NAME)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: Annotated[StrictStr, Field(min_length=1, max_length=MAX_QUESTION_CHARS)]


class FactBody(BaseModel):
    source: str | None
    statement: str


class UsageBody(BaseModel):
    input_tokens: int
    output_tokens: int


class PricingBody(BaseModel):
    input_per_million: str
    output_per_million: str
    currency: str


class ChatResponse(BaseModel):
    answer: str
    retrieved_doc_ids: list[str]
    facts_used: list[FactBody]
    decision: Decision
    usage: UsageBody
    pricing: PricingBody
    latency_ms: int


def create_app(configuration: Configuration) -> FastAPI:
    """The demo target answering in `configuration`; the instruction set is read now."""
    instructions = read_instruction_set(configuration.instruction_set)
    spec = configuration.spec
    pricing = PricingBody(
        input_per_million=spec.input_per_million,
        output_per_million=spec.output_per_million,
        currency=CURRENCY,
    )
    logger.setLevel(logging.INFO)
    app = FastAPI(title="Demo target", docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(RequestValidationError)
    async def refuse(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=REFUSAL)

    @app.post(CHAT_ROUTE)
    async def chat(body: ChatRequest) -> ChatResponse:
        answered = reply(configuration, instructions, body.question)
        return ChatResponse(
            answer=answered.answer,
            retrieved_doc_ids=list(answered.retrieved_doc_ids),
            facts_used=[
                FactBody(source=f.source, statement=f.statement) for f in answered.facts_used
            ],
            decision=answered.decision,
            usage=UsageBody(
                input_tokens=answered.input_tokens, output_tokens=answered.output_tokens
            ),
            pricing=pricing,
            latency_ms=answered.latency_ms,
        )

    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(RequestLogMiddleware, model=configuration.model.value)
    return app


class RequestLogMiddleware:
    """One line per HTTP request: route template, status and model, nothing else (R-206)."""

    def __init__(self, app: ASGIApp, model: str) -> None:
        self.app = app
        self.model = model

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status = 500

        async def send_and_record(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_and_record)
        finally:
            route = CHAT_ROUTE if scope["path"] == CHAT_ROUTE else UNMATCHED_ROUTE
            logger.info(json.dumps({"route": route, "status": status, "model": self.model}))


class BodyLimitMiddleware:
    """Refuses a body over `MAX_BODY_BYTES` with the contract's 422, before parsing (C-206)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        chunks: list[bytes] = []
        size = 0
        more = True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk: bytes = message.get("body", b"")
            size += len(chunk)
            if size > MAX_BODY_BYTES:
                await JSONResponse(status_code=422, content=REFUSAL)(scope, receive, send)
                return
            chunks.append(chunk)
            more = message.get("more_body", False)
        body = b"".join(chunks)
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)
