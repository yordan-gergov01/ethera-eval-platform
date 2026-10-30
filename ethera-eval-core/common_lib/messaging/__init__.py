"""The message contract between the backend and the runner.

Role: this package is the only interface between the two services: the envelope, the job
  payload base, the closed set of error codes, and the RabbitMQ topology.
Used by: `backend.messaging`, `backend.main`, `runner.main` and `runner.worker` import its
  modules directly.
Depends on: nothing itself; its modules use pydantic and aio-pika.
Key invariants: the backend and the runner never import each other (import-linter); everything
  they exchange is defined here. ORM-free (import-linter).
"""
