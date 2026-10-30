# Observability

Source: Bible Part III "Observability", brief §7.7, template D-005.

## Three planes, never mixed

| Plane | Where | Is evidence? |
|---|---|---|
| Audit | Database, append-only, same transaction as the change | yes |
| Technical logs | stdout, one JSON object per line (structlog), rotated by the runtime | no |
| Metrics | in memory, `/metrics`, internal only | no |

Audited actions: manifest changes, baseline promotions, simulations (clock advance, model
release, deprecation), notification handling, account administration.

## Log lines

- Correlation fields are injected by the formatter from contextvars, never passed by hand:
  `request_id`, `user_id`, `eval_run_id`, `client_id`, `project_id`, `source=harness`.
- `request_id` travels in every broker envelope, so runner lines correlate with the request.
- Route templates, never raw paths. One access line per request, after the response; probes
  excluded. Nothing in the observation layer may break a request.

## The never-log list (absolute)

Email addresses, names and free text, Golden inputs/outputs and product answers, query
strings, request and response bodies, auth and cookie headers, passwords and hashes, tokens,
webhook URLs, raw paths with IDs, SQL bound parameters (including inside tracebacks). UUIDs
are the allowed pseudonymous currency. Free text is logged by length only.

On any path where an exception can carry user data (DB errors render parameters, HTTP client
errors render URLs), log `type(exc).__name__`, never the traceback text.

## Metrics

Labels: route templates only; no client or project dimension; security counters
unlabelled. Known gaps are written down as owner calls.

## Production path (recorded, not built)

Ethera's internal framework (`openTelObserver(app)`, `openTelObserverWorker()`,
`record_cost()`, `register_enricher()`, keyed by `client.id` and `project.id`) is the
production adapter for the technical-log and metrics planes. Nothing is built for it in the
PoC (`docs/DECISIONS.md`).

## Mechanical checks

- `tests/integration/test_never_log.py` (real flows, captured handler output).
- `tests/unit/common_lib/test_logging_config.py` — redaction and formatter fields.
