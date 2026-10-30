"""Request IDs: one ID follows a request through the backend, the broker and the runner.

Role: the header name, the allowed pattern, generation and validation of request IDs.
Used by: `backend.api.middleware`, `backend.main` (CORS headers),
  `common_lib.messaging.envelope` (the envelope's `request_id` pattern).
Depends on: the standard library only.
Key invariants: request IDs travel in HTTP headers, message envelopes and log lines, so they are
  short and plain (`[A-Za-z0-9._-]{1,128}`); an incoming one is reused only if it matches
  (template_core D-005). ORM-free.
"""

import re
from uuid import uuid4

REQUEST_ID_HEADER = "X-Request-ID"

# Request IDs travel in HTTP headers, message envelopes and log lines, so they are
# kept short and plain.
REQUEST_ID_PATTERN = r"^[A-Za-z0-9._-]{1,128}$"
_REQUEST_ID_RE = re.compile(REQUEST_ID_PATTERN)


def new_request_id() -> str:
    """Generate a fresh request ID."""
    return uuid4().hex


def is_valid_request_id(value: str) -> bool:
    """Whether a client-supplied request ID is safe to reuse."""
    return _REQUEST_ID_RE.fullmatch(value) is not None
