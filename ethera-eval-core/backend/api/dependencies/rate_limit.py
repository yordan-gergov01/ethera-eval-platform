"""Rate limits on API requests.

Role: the `limit_requests` and `limit_login_attempts` dependencies. Every `/api/v1` request
  counts against the default rule, keyed by the user when the request carries a validly signed
  token and by the client address otherwise; login attempts also count against a stricter rule
  keyed by client address and username.
Used by: `backend.api.v1.router` (every `/api/v1` route, core and module) and
  `backend.api.v1.auth.router` (login).
Depends on: `RateLimiter` (via `backend.api.dependencies.services`), the token service and
  rate limit rules on `app.state` (set by `backend.main`), `RATE_LIMIT_STATE_KEY` from
  `backend.api.middleware`, `common_lib.schemas.identity.normalize_identifier`.
Key invariants: the key uses only the token's signature, not full authentication, which happens
  later. The bearer token is read by hand, not through `oauth2_scheme`, so public routes such as
  login are not documented as requiring a token. The client address is the one the proxy
  middleware already resolved from trusted proxies. When several rules apply, the request state
  keeps the tightest status for the headers. `/health` and `/docs` are never limited
  (template_core D-008).
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security.utils import get_authorization_scheme_param

from backend.api.dependencies.services import get_rate_limiter
from backend.api.middleware import RATE_LIMIT_STATE_KEY
from backend.services.rate_limit import RateLimiter, RateLimitRules, RateLimitStatus
from common_lib.schemas.identity import normalize_identifier

RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


async def limit_requests(request: Request, limiter: RateLimiterDep) -> None:
    """Count the request against the default rule; 429 when over the limit."""
    # The signature is enough to tell callers apart; authentication happens later.
    token = bearer_token(request)
    user_id = request.app.state.token_service.user_id_or_none(token) if token else None
    key = f"user:{user_id}" if user_id is not None else f"ip:{client_address(request)}"
    _record(request, await limiter.check(_rules(request).default, key))


async def limit_login_attempts(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    limiter: RateLimiterDep,
) -> None:
    """Count a login attempt per client address and username; 429 when over the limit."""
    key = f"{client_address(request)}:{normalize_identifier(form.username)}"
    _record(request, await limiter.check(_rules(request).login, key))


def bearer_token(request: Request) -> str | None:
    """The bearer token, read as `oauth2_scheme` reads it.

    Not taken from `oauth2_scheme` itself: this dependency runs on every route, and a
    security dependency here would mark public routes such as login as requiring a token
    in the API documentation. Protected routes declare it through `get_current_user`.
    """
    authorization = request.headers.get("Authorization")
    scheme, token = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != "bearer":
        return None
    return token


def client_address(request: Request) -> str:
    """The client's address, already resolved from trusted proxies by the middleware."""
    return request.client.host if request.client is not None else "unknown"


def _rules(request: Request) -> RateLimitRules:
    rules: RateLimitRules = request.app.state.rate_limit_rules
    return rules


def _record(request: Request, status: RateLimitStatus) -> None:
    # Several rules can apply to one request; the headers describe the tightest one.
    current: RateLimitStatus | None = getattr(request.state, RATE_LIMIT_STATE_KEY, None)
    if current is None or status.remaining < current.remaining:
        setattr(request.state, RATE_LIMIT_STATE_KEY, status)
