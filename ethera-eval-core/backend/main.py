"""Application factory: `uvicorn backend.main:create_app --factory`.

Role: builds the FastAPI app of the platform core — settings, logging, process-wide components
  on `app.state`, the startup lifespan (migrations and seeding under the startup lock, the broker
  connection, the rate limit cleanup task), exception handlers, routers and middleware — with any
  domain modules it is given.
Used by: the `backend` barrel (`create_app`), and through it `evals.app.create_app` (the
  production entry point); the integration and unit tests that need the core app alone.
Depends on: `backend.api` (errors, health, middleware, v1 routers), `backend.core` (database,
  modules, periodic, security, settings, startup, tokens), `backend.messaging.connection`,
  `backend.services` (rate_limit, seeding), `common_lib` (logging, broker connector, settings).
Key invariants: boots complete with no modules (tests/integration/test_boot_without_evals.py).
  Migrations and seeding run once across replicas under the startup lock (template_core D-004).
  The broker connection starts in the background even with nothing to publish, to declare the
  topology (template_core D-010); the API works without the broker. No publisher, consumer,
  job waiter or sweeper is started yet — they are wired in slice 003 (D-006). Middleware is
  added innermost first; the proxy middleware is outermost and only with trusted proxies.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import timedelta

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from backend.api.errors import RATE_LIMIT_HEADERS, register_exception_handlers
from backend.api.health import router as health_router
from backend.api.middleware import (
    BodySizeLimitMiddleware,
    RateLimitHeadersMiddleware,
    RequestContextMiddleware,
    UnhandledErrorMiddleware,
)
from backend.api.v1.router import api_router, module_api_router
from backend.core.database import DATABASE_UNAVAILABLE_ERRORS, close_database, init_database
from backend.core.modules import ModuleMount
from backend.core.periodic import periodic_task
from backend.core.security import Argon2PasswordHasher
from backend.core.settings import BackendSettings
from backend.core.startup import apply_migrations, startup_lock
from backend.core.tokens import JwtTokenService
from backend.messaging.connection import BrokerConnection
from backend.services.rate_limit import RateLimitRule, RateLimitRules, build_rate_limiter
from backend.services.seeding import AdminAccount, build_seeding_service
from common_lib.logging_config import configure_logging
from common_lib.messaging.connection import robust_connector
from common_lib.request_id import REQUEST_ID_HEADER
from common_lib.settings import load_settings

SERVICE_NAME = "backend"
RATE_LIMIT_CLEANUP_TASK = "rate_limit_cleanup"
RATE_LIMIT_CLEANUP_INTERVAL_SECONDS = 60

logger = structlog.get_logger(__name__)


def create_app(
    settings: BackendSettings | None = None, *, modules: Sequence[ModuleMount] = ()
) -> FastAPI:
    """Build the application. Settings are read from the environment unless given.

    `modules` are the domain modules to mount (routers, models, migrations); the core runs
    complete without any. `evals.app.create_app` passes `evals.MODULES`.
    """
    settings = settings or load_settings(BackendSettings)
    configure_logging(
        service=SERVICE_NAME, level=settings.log_level, log_format=settings.log_format
    )

    hasher = Argon2PasswordHasher()
    token_service = JwtTokenService(
        secret=settings.jwt_secret,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        lifetime=timedelta(minutes=settings.access_token_expire_minutes),
        leeway=timedelta(seconds=settings.jwt_leeway_seconds),
    )
    rate_limit_rules = RateLimitRules(
        default=RateLimitRule(
            name="default",
            requests=settings.rate_limit_default_requests,
            window_seconds=settings.rate_limit_default_window_seconds,
        ),
        login=RateLimitRule(
            name="login",
            requests=settings.rate_limit_login_requests,
            window_seconds=settings.rate_limit_login_window_seconds,
        ),
    )

    # Started even with nothing to publish yet: it declares the topology, so a job
    # published before the runner first starts is never unroutable (D-010).
    broker = BrokerConnection(robust_connector(settings, connection_name=SERVICE_NAME))
    # JobPublisher, JobConsumers, the stale-job sweeper (rebuilt for Eval Runs) and JobWaiter
    # (with the poll limiter):
    # Wired in slice 003 (EvalTrialBatchRequested); see docs/DECISIONS.md D-006.

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Migrations and seeding run once across all replicas, under the startup lock.
        async with startup_lock(settings):
            await apply_migrations(settings, modules)
            await init_database(settings, modules)
            try:
                await build_seeding_service(hasher).seed(
                    AdminAccount(
                        username=settings.admin_username,
                        email=settings.admin_email,
                        password=settings.admin_password,
                    )
                )
            except BaseException:
                await close_database()
                raise
        # The broker is reached in the background; the API works without it.
        broker.start()
        logger.info("startup_complete")
        try:
            async with periodic_task(
                RATE_LIMIT_CLEANUP_TASK,
                interval_seconds=RATE_LIMIT_CLEANUP_INTERVAL_SECONDS,
                action=lambda: build_rate_limiter().delete_expired_windows(rate_limit_rules),
            ):
                yield
        finally:
            await broker.close()
            await close_database()
            logger.info("shutdown_complete")

    app = FastAPI(
        title="Ethera Eval Platform backend",
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_api_docs else None,
        openapi_url="/openapi.json" if settings.enable_api_docs else None,
        redoc_url=None,
    )

    # Process-wide components, used by the service wiring in backend.api.dependencies.
    app.state.password_hasher = hasher
    app.state.token_service = token_service
    app.state.rate_limit_rules = rate_limit_rules
    app.state.broker = broker

    register_exception_handlers(app, database_unavailable=DATABASE_UNAVAILABLE_ERRORS)
    app.include_router(health_router)
    app.include_router(api_router)
    for module in modules:
        if module.router is not None:
            app.include_router(module_api_router(module.router))

    # Starlette runs the last added middleware first, so this list is innermost first.
    # Request context wraps everything (every response has a request ID and an access
    # line); CORS wraps every response a client can receive, including 413 and 500.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(RateLimitHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "Retry-After", "Location", *RATE_LIMIT_HEADERS],
    )
    app.add_middleware(RequestContextMiddleware)
    if settings.trusted_proxies:
        # Outermost, so everything inside sees the real client address. Uvicorn's own
        # proxy handling is switched off in the Dockerfile; this one is configured here.
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=list(settings.trusted_proxies))
    return app
