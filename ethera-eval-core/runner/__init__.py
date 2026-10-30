"""The evaluation runner: an asyncio worker with no ports and no database access.

Role: package marker for the runner service (process entry, settings, worker, heartbeat).
Used by: `python -m runner.main` (the runner image's CMD).
Depends on: nothing itself; its modules use `common_lib` and aio-pika.
Key invariants: import-linter forbids the runner importing `common_lib.models`, `tortoise`,
  `backend` or `evals`; it talks to the backend only through the message contract in
  `common_lib.messaging` (template_core D-011).
"""
