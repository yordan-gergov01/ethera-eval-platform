# Decision log (inherited from template_core)

These are template_core's own decisions (commit `e1d773d`), kept as the history of the
platform core and cited elsewhere as "template_core D-0xx". The repository's decisions live in
`../../docs/DECISIONS.md`. Where this project changed course:

- D-011, D-012 and D-013 describe the template's LLM service, mock provider and model switch:
  the provider and the model switch were removed with the prompt jobs, and `llm/` became
  `runner/` (repository D-004).
- D-009 and D-010 describe reliable jobs and long polling for prompt jobs: the machinery is
  kept payload-generic and is wired for Eval Runs in slice 003 (repository D-006).
- D-004 (built-in Tortoise migrations) is extended to one app label and migrations package
  per domain module (repository D-007).

## Open questions from the brief

### D-009: Delivering asynchronous results to the client

- **Context:** An answer from the LLM service arrives seconds after the prompt was submitted. The brief leaves open how the frontend learns that it is ready, and the backend runs as several replicas, so the result may be stored by a different replica than the one the client is talking to. The client side is recorded in template_web D-006.
- **Options considered:** Short polling - simple, but either slow or many requests; long polling - one request waits until the result arrives or a timeout passes, plain HTTP; server-sent events or WebSockets - push without polling, but long-lived connections through every proxy, extra client and server code, and still a cross-replica signal; synchronous request-reply over RabbitMQ - holds an HTTP request and a broker reply queue for the whole job.
- **Decision:** `POST /api/v1/prompts` answers 202 with the job and a `Location`; the client long-polls `GET /api/v1/prompts/{id}?wait_seconds=N` (at most 25 seconds), which always answers 200 with the job's current state. The transaction that stores a result sends a PostgreSQL `NOTIFY`; each backend replica keeps one connection listening and wakes its own waiting requests, which then read the job. No database connection is held while waiting. A user may have three polls waiting per replica.
- **Consequences:** Plain HTTP and JSON that work through any proxy, results delivered within moments across replicas, and no extra infrastructure. Each waiting poll holds an open request; the per-replica cap bounds that, and each poll counts once against the rate limit. If the listening connection drops, waiters are woken to read again, so a result is late at worst, never lost.
- **With more time:** Server-sent events for streaming partial answers once a real model produces them.

### D-003: Message format and queue layout

- **Context:** The backend and the LLM service talk only through RabbitMQ, in both directions. The format must be validated on both sides, evolve safely, and let each result be matched to its request; the layout must keep failing messages from blocking or looping forever.
- **Options considered:** Protobuf or Avro - compact and strongly versioned, but needs a schema toolchain both services must share; plain JSON validated by shared Pydantic models - readable in the broker and in logs, and both services already depend on the shared library. A topic exchange or one queue per model - more flexible routing that nothing here needs; one direct exchange with one queue per direction - simple and enough. Classic queues with requeue on failure - a poison message can loop forever; quorum queues with a delivery limit and dead-letter queues - failures stop after a few attempts and stay inspectable.
- **Decision:** Every message is a versioned JSON envelope (schema version, message ID, message type, correlation ID, request ID, UTC timestamp, payload), defined once in the shared library and validated strictly on both sides. The correlation ID is the job ID, so results are matched without extra state. One direct exchange carries job requests and job results to one quorum queue each; after three failed deliveries a message moves to a dead-letter queue. Failures cross the boundary only as a closed set of error codes.
- **Consequences:** Messages are self-describing and easy to inspect, and a contract change is a code change covered by tests in one place. JSON is larger than a binary format, which does not matter at this volume. A new schema version needs both services to accept it before senders switch.
- **With more time:** Contract tests that run the backend's and the LLM service's message handling against recorded messages of each schema version.

### D-011: The LLM service has no database access

- **Context:** The brief leaves open whether the LLM service reads or writes the database. It needs a job's prompt and model to answer it, and the backend needs the answer.
- **Options considered:** The LLM service writes results to the database directly - one hop fewer, but a second writer of the job table, database credentials and a network path in a service that talks to an outside provider; the LLM service is stateless and talks only through RabbitMQ - the message carries everything it needs, and only the backend owns the data.
- **Decision:** The LLM service has no database credentials, no network path to PostgreSQL and no ports: it is on the internal messaging network only. Each job message carries the prompt and the model; the result goes back as a message, and the backend alone stores it. An import contract keeps database code out of the service.
- **Consequences:** The component that will hold a provider API key and reach the internet cannot read or change any data, and it scales by running more workers without touching the database. The backend stays the single place where job state changes, which keeps idempotency and the long-poll notifications in one service. A result takes one extra hop through the broker.
- **With more time:** If retrieval-augmented generation is added, the backend passes the retrieved context in the job message, so the LLM service still needs no database access.

### D-004: Applying database schema changes

- **Context:** The schema must be created on a fresh install and changed safely over time, and several backend replicas may start at the same moment.
- **Options considered:** Creating tables from the models at startup - no history, cannot change existing tables; Aerich - the established migration tool for Tortoise (0.10.1 supports Tortoise 1.x), but an extra dependency with its own command line and configuration; the migration framework built into Tortoise 1.x - no extra dependency, plain Python migration files with raw SQL support and a programmatic API, but still marked experimental.
- **Decision:** Use Tortoise's built-in migrations. Migration files are generated from the models, reviewed and committed; the first one enables pgvector. The backend applies pending migrations at startup while holding a PostgreSQL advisory lock, so with several replicas exactly one applies them and the others wait and find nothing to do. Each migration runs in its own transaction.
- **Consequences:** A fresh database and an existing one reach the same schema the same way, and the history of every change is in the repository. The framework's experimental status is a known risk, mitigated by pinning the exact Tortoise version with hashes, keeping migrations as plain reviewed files, and recording applied migrations in the database; if the framework changes incompatibly, the existing files remain readable and can be ported. A failed migration rolls back and stops that replica from starting.
- **With more time:** Run migrations as a one-off job before new replicas start, and fail the test suite when the models and the migration files disagree.

### D-013: Switching the model

- **Context:** The brief requires that an administrator can switch the model and leaves open how the change reaches the LLM service and whether it survives a restart. Several LLM workers may run, and jobs may already be queued.
- **Options considered:** A configuration message broadcast to every worker - immediate, but each worker keeps state that is lost on restart and missed by workers that start later; an environment variable on the LLM service - survives restarts, but needs a redeploy and is not changeable through the API; the current model stored in the database and stamped on every job message - no worker state, one read per prompt.
- **Decision:** The backend stores the current model in a single database row, changeable only with `llm:model:change` and only to a model in `LLM_ALLOWED_MODELS`. Every job message carries the model the job was requested with, and the LLM service checks it against its own allowed list. The change, the acting user and the previous model are logged.
- **Consequences:** A change applies to the next job without a restart, survives restarts of either service and works with any number of workers. Jobs already queued keep the model they were requested with. Both services read the same LLM_ALLOWED_MODELS from the environment; a job with a model the LLM service does not allow fails with UNSUPPORTED_MODEL. A stored model removed from the allowed list is reset to LLM_DEFAULT_MODEL at the next start, with a warning.
- **With more time:** A history of model changes in an audit table, and a per-request model choice for users who are allowed one.

### D-008: Rate limiting

- **Context:** The brief requires rate limiting but leaves open what is counted, which endpoints are limited and where the counters live. With several backend replicas, limits kept in each process's memory would multiply by the number of replicas.
- **Options considered:** Fixed window - simplest, but allows twice the limit around a window edge; sliding log - exact, but stores every request; sliding window counter - two counters per key and a close estimate. Counters in process memory - fast, but per replica and lost on restart; Redis - the usual shared store, but a sixth service where the brief describes five containers, and one more thing to run and secure; PostgreSQL - already present and shared, one atomic statement per request. Keying signed-in requests by user and address - users behind one NAT would share a quota and moving users would get a fresh one; by user only - the quota follows the account.
- **Decision:** A sliding window counter in an unlogged PostgreSQL table, updated with one atomic `INSERT ... ON CONFLICT` per request and cleaned up by a background task. Every `/api/v1` request counts against 120 per 60 seconds, per user when the token has a valid signature and per client address otherwise; login also counts against 5 per 60 seconds per client address and username. Rejected requests count too. `/health` and `/docs` are not limited. Over the limit is a 429 with `Retry-After` and `X-RateLimit-*` headers, all in seconds. `X-Forwarded-For` is used only from addresses in `TRUSTED_PROXIES`. If the database is unavailable, the check fails like any other request (503).
- **Consequences:** Limits hold across any number of replicas without new infrastructure, at the cost of one small write per request. Because the login key combines client address and username, an attacker cannot lock out a user who logs in from another address; guesses spread over many addresses are not stopped by this rule. Behind Docker's port publishing all external clients may appear as one address, so anonymous requests share one limit in local development; behind a real reverse proxy, `TRUSTED_PROXIES` gives each client its own limit. A database crash empties the unlogged table, which only resets the limits.
- **With more time:** A per-account login limit with growing delays that does not depend on the address, separate limits for expensive endpoints, and a dedicated store such as Redis once the write per request matters.

### D-014: Dependency management, linting and formatting

- **Context:** The brief leaves open how dependencies are managed and how code style is checked. Two services with different dependencies share one library, the images must be reproducible, and development happens on Windows while the containers run Linux.
- **Options considered:** Poetry, PDM or uv as the project manager - lock files, but their own installer that every contributor and image needs; pip with hand-written requirement files - no lock for transitive dependencies; pip-tools - pinned, hashed files, but resolved for the host platform only, so a file compiled on Windows breaks the Linux images; `uv pip compile --universal` - pinned, hashed files valid on every platform, with pip remaining the installer. For style: flake8, isort and black - three tools; ruff - one tool for linting and formatting.
- **Decision:** One root project keeps `backend/`, `runner/` and `common_lib/` side by side. Each service's direct dependencies are listed in `requirements/<service>.in` and compiled with `uv pip compile --universal --generate-hashes` into pinned, hashed files; pip installs them with `--require-hashes`, and each image installs only its own file. ruff lints and formats, mypy runs in strict mode, and import-linter enforces the layering, the absence of database code in the API layer and the LLM service, and an ORM-free shared library. pre-commit runs these with gitleaks before every commit.
- **Consequences:** The same commit always builds the same images, and each image contains only what its service needs. The brief's structural rules, such as an API layer without database calls, are checked on every commit instead of by review. uv is one more development tool, used for a single command. The type and contract checks run from the local virtual environment, so hooks need it installed.
- **With more time:** A CI pipeline that runs the same checks and the Docker test suite on every push, and automated dependency updates with a vulnerability scan.

## Additional decisions

### D-001: Separate database role for the application

- **Context:** The PostgreSQL image creates one superuser. An application that connects as a superuser can bypass every permission in the database, which contradicts least privilege.
- **Options considered:** Connect as the superuser - simplest, but any flaw in the backend gets full control of the server; a dedicated non-superuser role created by an init script - one extra script and credential pair, but the backend can only work inside its own database.
- **Decision:** On first start an init script creates a login role without superuser, role-creation or database-creation rights, makes it the owner of the application database, and enables the vector extension as the superuser. The backend receives only this role's credentials.
- **Consequences:** The backend can create and migrate its own schema but cannot create roles, databases or extensions. Init scripts run only on an empty volume, so changing database credentials requires resetting the volume (`docker compose down -v`) in local development.
- **With more time:** Split the role further into a migration owner and a runtime role with only data privileges.

### D-002: Least-privilege access to RabbitMQ

- **Context:** Each service needs its own broker credentials, limited to what it uses, and credentials must come from the environment, never from the repository. Dead-lettered messages must be readable for investigation without exposing the broker outside the container network.
- **Options considered:** One shared user via the image defaults - simple, but every service could do everything; a one-shot init container creating users - needs a bootstrap admin credential and an extra service; a definitions file rendered from environment variables at broker start - one small start-up script, no admin user, no extra service.
- **Decision:** A start-up script renders the vhost, users and permissions from environment variables into a tmpfs, and the broker imports them at boot. Permissions follow the message topology, so each service can only declare, publish to and consume from what it owns. No guest user exists. The management plugin is included without a published port; a dedicated inspector user can only read the two dead-letter queues from inside the container.
- **Consequences:** Broker access is declarative, identical on every start, and never stored in the repository or the image. Users removed from the configuration are not deleted from an existing volume. Dead letters can be read with one command, but only from the Docker host.
- **With more time:** Docker secrets instead of environment variables, credential rotation without a restart, an alert on dead-letter queue length, and a documented replay procedure.

### D-005: Error responses and logging

- **Context:** The brief requires consistent, meaningful error responses with internal details kept in the logs, but leaves the error format and the logging design open. A request also needs to be traceable across the backend and the LLM service.
- **Options considered:** FastAPI's default error bodies - different shapes for framework and validation errors, no stable codes; a custom error shape - consistent, but every client has to learn it; RFC 9457 problem details - a published standard with room for a stable code and the request ID. For logging: the standard library with a JSON formatter - no dependency, but context and library logs need custom plumbing; structlog on top of the standard library - one dependency, with context variables, processors, and library logs in the same pipeline.
- **Decision:** Every error response is problem details with a stable machine-readable code and the request ID, produced in one module that maps application errors to status codes; services raise errors by meaning and know nothing about HTTP. Unexpected exceptions return a generic 500 and are logged once with their full chained traceback. Logs are structured with structlog: JSON lines to stdout in containers, readable console output locally, each line with a UTC timestamp, level, service, logger and request ID, and sensitive keys redacted. The request ID is taken from X-Request-ID or generated, returned to the client, and carried in every message to the LLM service.
- **Consequences:** Clients handle every error the same way and branch on the code, not on message text; any failure can be found in the logs by the request ID the client received. Validation errors never echo submitted values. Redaction is a safety net only; code still must not log secrets.
- **With more time:** Ship the logs to a central store with search and alerting, and publish the catalogue of error codes in the API documentation.

### D-006: Authentication and authorization

- **Context:** The brief requires hashed passwords with a strength rule, signed expiring tokens, roles and permissions stored in the database, checks by permission rather than role, 401 and 403, and no login for inactive users. It leaves open how passwords are hashed, what the strength rule is, what a token contains, and how tokens are revoked. The server side of logout is recorded here; where the browser keeps the token is recorded in template_web D-003.
- **Options considered:** Hashing: bcrypt - widely used, but limited to 72 bytes; Argon2id - memory-hard, the current OWASP recommendation. Strength rule: composition rules - push users towards predictable patterns; NIST SP 800-63B - length plus a list of common passwords. Token contents: permissions in the token - no database read per request, but stale until the token expires; only the user ID and a token version - one lookup per request, changes apply immediately. Revocation: a list of revoked tokens - storage per token; a token version per user - one integer, revokes all of a user's tokens at once.
- **Decision:** Passwords are normalised to NFKC and hashed with Argon2id; hashes are upgraded on login when the parameters change. A password is 12 to 128 characters, not on the NCSC list of common passwords, and not equal to the username or email, with no composition rules. Access tokens are HS256 JWTs valid for 30 minutes that carry only the user ID and token version; every request loads the user, its role and its permissions, and logout increments the token version. Permissions are defined in code and synced to the database at startup; endpoints declare permissions and never check role names. Every failed login gets the same 401 while the reason is logged, and an unknown username costs a full password verification.
- **Consequences:** Deactivation, logout and role changes take effect on the next request, at the cost of a few indexed reads per request. Logout ends every session of the user, not only the current device. Without refresh tokens, users log in again when the token expires.
- **With more time:** Refresh tokens in HttpOnly cookies with per-session revocation, multi-factor authentication for admins, and asymmetric signing if other services ever need to verify tokens.

### D-007: User accounts and administration

- **Context:** The brief requires managing users by permission but leaves open how accounts are identified, whether they can be deleted, and how administrators are kept from locking everyone out.
- **Options considered:** Sequential integer IDs - short, but guessable and they reveal the number of accounts; UUIDv4 - opaque and safe to expose. Deleting users - simple, but breaks references to their jobs and history; deactivating them - every reference stays valid, at the cost of keeping inactive rows. Protecting the last administrator by role name - contradicts checking permissions instead of roles; protecting the last active holder of the permission that manages accounts - keeps working for any future role.
- **Decision:** All identifiers are UUIDv4. Accounts are deactivated, never deleted; there is no delete permission or endpoint, and a deactivation applies to the next request. Nobody can change their own role or active status (403), while everyone may change their own name and email. A demotion or deactivation is applied only if at least one active account still holds `users:update` (409); a transaction-scoped advisory lock serialises these changes, so concurrent requests cannot remove the last holder together. Each operation has its own request schema that rejects unknown fields, so a role cannot be set through the self-service endpoint.
- **Consequences:** References and history stay valid, and no administrator can lock themselves or everyone else out. Usernames and emails of inactive accounts stay reserved. A role change does not end the user's sessions; it changes what the next request may do.
- **With more time:** An audit log of account changes with the acting user, and anonymisation of deactivated accounts on request.

### D-010: Reliable job processing

- **Context:** Jobs cross a broker and a second service, either of which may be down, slow or restarted. A job must never stay pending forever, a message must never loop forever, and a duplicate must never change a result. This refines D-002.
- **Options considered:** Publish first and store afterwards - a crash in between loses the job; store first and publish afterwards - the job always exists, and a failed publish can be recorded on it. Dead-letter settings as queue arguments - kept in code, but declaring such a queue needs read permission on it; as broker policies - declarable without read, changeable without re-creating queues, but defined in the broker provisioning. Only the consumer declares its queue - least privilege, but jobs published before the LLM service first starts are dropped as unroutable; the backend declares it as well - nothing is dropped.
- **Decision:** A job is stored pending before it is published, with publisher confirms and as mandatory; if the broker cannot take it, the job fails with `BROKER_UNAVAILABLE` and the client gets 503. Delivery is at least once; results apply only to pending jobs, so duplicates change nothing. The backend declares the job queue too, with configure and write permission but no read. Dead-lettering and a limit of three deliveries are broker policies. Invalid messages are rejected to a dead-letter queue; the backend fails dead-lettered requests with `UNDELIVERABLE` and keeps unreadable results in their dead-letter queue for inspection. A result that cannot be stored because the database is down is requeued after a pause. A sweeper fails jobs still pending after `JOB_TIMEOUT_SECONDS` with `TIMED_OUT`. Both services retry the first broker connection with exponential backoff and then reconnect automatically, and the backend waits for a healthy broker through `depends_on`.
- **Consequences:** Every job ends completed or failed with a stated reason, and nothing is lost silently. Configure permission on the job queue also lets the backend delete it: a small, scoped exception to least privilege. The dead-letter settings live in the broker provisioning, kept in step with the code by a test. RabbitMQ 4 counts only consumer crashes towards the delivery limit, not explicit requeues, so the LLM service must reject rather than requeue a message it cannot process. A result that arrives after the sweeper has failed its job is ignored by design, so a very slow model can show a timeout although an answer arrived later; `JOB_TIMEOUT_SECONDS` is the setting for that.
- **With more time:** A replay procedure for dead-lettered messages, an alert on dead-letter queue length, and an outbox table so a publish is retried instead of failing the job when the broker is briefly down.

### D-012: A mock provider only

- **Context:** The brief states that a mock provider returning a canned answer is enough and a real provider is optional. The model must still be switchable, and the project must run on a clean machine with only Docker.
- **Options considered:** A real provider - realistic, but needs a key, network egress and costs, and tests depend on an outside service; a local model - no key, but a large image and slow, hardware-dependent answers; a mock behind the same interface as a real provider - deterministic and free, and it exercises the whole asynchronous flow.
- **Decision:** `MockProvider` is the only provider: it answers with a canned text that names the model, after a configurable delay, and fails a configurable share of answers. Providers implement one interface and are chosen by name from a registry, so a real one is one class and one registry entry; the README describes the steps.
- **Consequences:** Everything around the model (queues, timeouts, failures, model switching, long polling) is tested end to end without external dependencies. The answers say nothing about real model quality, latency or cost.
- **With more time:** The provider API key as a Docker secret, and outbound traffic allowed only to the provider and only for the llm container. PII filtering and a clear system/user boundary against prompt injection. Token usage per answer, with a daily token quota per user next to the rate limit. Retries with backoff on provider 429 and 5xx responses, and a circuit breaker. Evaluations on a fixed prompt set before switching models, plus latency, error and cost metrics per model.

### D-015: Network layout enforcing the communication rules

- **Context:** The brief fixes who may talk to whom: the frontend only to the backend, the backend and the LLM service only through RabbitMQ, and only the backend to the database. It does not say how this is enforced, and the separation must hold even from a container in the frontend's own stack.
- **Options considered:** One default Compose network - every container reaches every other, so the rules hold only by convention; one internal network per relationship - enforced by Docker without extra components; network policies or a service mesh - stronger controls that need an orchestrator.
- **Decision:** Three networks. `edge` holds only the backend and is the only network with a published port. `data` (internal) holds the backend and PostgreSQL, and `messaging` (internal) holds the backend, RabbitMQ and the LLM service. PostgreSQL, RabbitMQ and the LLM service publish no ports, and the frontend joins none of these networks. The browser calls the backend's published port. The API documentation (`/docs`, `/openapi.json`) is public when `ENABLE_API_DOCS` is true, because it shows the API's shape and no data, and it is switched off with `false`.
- **Consequences:** The LLM service has no route to the database or to the internet, and nothing outside the stack can reach the broker, the database or the LLM service. A real provider needs an extra network with outbound access for the LLM container only. Inspecting the database or the broker from the host goes through `docker compose exec`.
- **With more time:** TLS for the connections to PostgreSQL and RabbitMQ, and the API documentation disabled by default outside local development.

## What I would change with more time

**Database scaling**

- PgBouncer in transaction mode in front of PostgreSQL once replicas x `DB_POOL_MAX_SIZE` approaches `max_connections` (about ten replicas at the defaults), so many backend connections share few server connections; the job-event listener keeps a direct connection, because `LISTEN` does not work through transaction pooling.
- Read replicas for read-heavy endpoints such as user lists and job reads without waiting, when reads dominate the primary's load; long polls stay on the primary, because a replica may lag behind the `NOTIFY` that woke them.
- Monthly partitions of `prompt_jobs` with a retention policy that drops old partitions, once the table reaches tens of millions of rows or vacuum and the sweeper's index scans slow down; dropping a partition is far cheaper than deleting rows.
- Sharding by user ID only if one primary on the largest practical instance can no longer take the write load after the steps above; the signal is sustained write latency or WAL volume at that size, not table size alone.

**LLM and AI**

- A real provider behind the existing interface (D-012, README steps) as soon as the system must give useful answers rather than demonstrate the flow.
- Offline evaluation on a curated, anonymised dataset built from real prompts with reference answers, scored for correctness, format and latency before every model switch (extends D-012), so changing `LLM_ALLOWED_MODELS` becomes a measured decision.
- Online evaluation once traffic is large enough for differences to be significant: automatic scoring of a sample of live answers, user feedback on each answer, and a small share of traffic sent to a candidate model to compare it with the current one.
- If retrieval-augmented generation is added: embeddings in pgvector (already enabled), a chunking strategy tested on the real documents, an HNSW index once exact search gets slow, and evaluation of retrieval (are the right chunks found) and groundedness (is the answer supported by them).

**Cost**

- Token accounting per job and per-user token quotas (D-012) from the first paid provider on, because the request rate limit counts requests, not cost, and one long prompt can cost as much as hundreds of short ones.
- Response caching keyed by model and normalised prompt, once repeated prompts are a noticeable share of traffic; per user only, since answers may contain personal data.
- Routing simple prompts to a cheaper model by length or a small classifier, once cost per answer matters more than uniform quality, validated on the offline evaluation set first.

**Security**

- Prompt-injection defences and PII redaction (D-012) are a precondition for the first external provider, not an improvement after it.
- An append-only audit log of admin actions, covering account changes (D-007) and model switches (D-013), once more than one person administers the system.
- Secrets in a secret store with rotation (D-002), and TLS between services (D-015), as soon as the system runs on more than one host or outside a developer machine.
- Dependency and image vulnerability scanning (pip-audit and an image scanner) that fails the CI build on known critical issues (D-014).
- Confirm an email change with the current password and a verification link sent to the new address.

**Operations**

- Metrics and tracing with OpenTelemetry before production use: latency and error rate per endpoint, depth of `runner.jobs` and both dead-letter queues, and job duration per model, with the trace context carried in the message envelope next to the request ID (D-005). Alerts fire on any message in a dead-letter queue, on `runner.jobs` growing for several minutes, and on a rising 5xx rate.
- CI running the full Docker test suite on every push (D-014) as soon as a second person contributes.
- A reverse proxy or load balancer in front of the backend replicas, so several replicas serve one address.
