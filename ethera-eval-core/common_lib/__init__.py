"""Code shared by the backend and the runner.

Role: package marker for the shared library: errors, logging, settings, request IDs,
  permissions, schemas, the message contract, and the ORM models (backend only).
Used by: `backend`, `runner` and `evals` import its modules directly.
Depends on: nothing itself.
Key invariants: import-linter keeps everything outside `common_lib.models` ORM-free, because the
  runner image copies all of `common_lib` but installs no ORM (a new module is added to that
  contract); the core never imports `evals`.
"""
