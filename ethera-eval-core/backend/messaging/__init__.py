"""RabbitMQ infrastructure of the backend: connection, publisher and consumers.

Role: package marker for the backend's broker side.
Used by: `backend.main` imports `backend.messaging.connection`.
Depends on: nothing itself; its modules use aio-pika and `common_lib.messaging`.
Key invariants: import-linter forbids it importing `backend.api` or `fastapi` ("Messaging never
  imports the API"), and services never import it. Only the connection is started today; the
  publisher and consumers are generic and wired in slice 003 (D-006).
"""
