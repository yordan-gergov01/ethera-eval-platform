# Fix registry

The project's defect memory (Bible Phase 7; rules in `.claude/rules/fix-registry.md`).

## The two-artifact rule

A fix is finished only with BOTH artifacts:

1. a **sealing regression test** named for the invariant (never the mechanism), proven by a
   mutation check — revert the fix, the seal goes red; restore it, the seal goes green; and
2. a **row in this table** — when the defect shipped (lived in committed code).

A fix with only one of them is unfinished: not done, not committed.

## Scope

- Defects that **shipped** get a row. A defect caught in a run's own uncommitted code gets
  the sealing test but no row. A committed twin found along the way gets a row.
- Before fixing anything, check this table and the `CLAUDE.md` ledger: the "bug" may be
  documented deliberate behaviour.
- A revising fix references the old ID; the old row is marked `superseded by FIX-NNN`.
  Seals are never weakened; changing a sealed invariant is an owner decision recorded in the
  superseding row.
- The commit column is filled by a follow-up commit once the fix ships.

## Registry

| ID | Date | Scenario and root cause | Found by | Seal (test name) | Severity | Commit |
|---|---|---|---|---|---|---|
| FIX-001 | 2026-10-31 | Sealed oracle case `whitespace` of the equal-Manifest test produced invalid YAML (doubling every indent misaligns sibling keys under `- `), so it demanded a 200 for a document every safe YAML loader refuses. Root cause: the test author did not load the variant before sealing. Fixed by re-sealing that one expression (owner approval). | wave 2 implementer, confirmed by Claude with PyYAML | `test_equal_manifest_returns_the_current_version_unchanged[whitespace]` | minor | (pending) |
| FIX-002 | 2026-10-31 | Usernames reached the technical logs (never-log list: names). The admin seed logged `admin_account_exists` / `admin_account_created` with `username=` at every start (in the lifespan, before any request), and `login_failed` logged whatever username was typed (possibly a mistyped password). Root cause: template log events keyed by username instead of the pseudonymous user ID. Fixed: the seed logs the admin's `user_id`; `login_failed` logs `username_length` only. | security-privacy-lens + adjudicator | `test_logs_never_carry_a_username` | critical | pending |
| FIX-003 | 2026-10-31 | `UnhandledErrorMiddleware` logged `logger.exception(..., path=scope["path"])`: the raw path (IDs, slugs) and the exception chain's messages, which on a real path carry SQL bound parameters (`GET /api/v1/users?offset=100000000000000000000` logged `invalid input for query argument $2: 100000000000000000000`). Committed twin in the same file: the access line logged the raw path on every request. Root cause: template_core D-005 logged full tracebacks and raw paths, contrary to observability.md (route templates; `type(exc).__name__` on paths whose errors carry user data). Fixed: both lines log the matched route template (no path when none matched); the unhandled line logs `error_type` and `error_chain` (type names), no message or traceback. | adjudicator | `test_unhandled_errors_log_neither_raw_paths_nor_exception_text` | major | pending |
| FIX-004 | 2026-10-31 | `GET /api/v1/users?offset=100000000000000000000` passed `Query(ge=0)` and failed int8 encoding in asyncpg: a 500 instead of an empty page. Root cause: the offset went to SQL unbounded. Fixed: the repository caps it at 2^63-1 (`MAX_SQL_OFFSET`), the API keeps accepting any offset ≥ 0 and echoes the caller's value. The registry's `/api/v1/products` had the same defect (uncommitted, fixed with the same seal). | functional-spec-lens (twin) | `test_list_offset_beyond_int64_answers_empty_page_not_500` | minor | pending |
| FIX-005 | 2026-10-31 | Twin of FIX-003 in the error handlers: `database_unavailable` (503 for driver connection errors) and `request_failed` (5xx application errors) logged with `exc_info=exc`, so the exception chain's messages reached the logs; driver messages carry host names and SQL bound parameters (never-log list), and a 5xx `AppError` raised from a driver error carries that error as its cause. Root cause: template_core D-005 logged full tracebacks on handled server errors. Fixed: both log `error_type` and `error_chain` (type names only) through the shared `exception_chain`. | Claude (twin, found by the FIX-003 implementer) | `test_handled_server_errors_log_type_names_not_exception_text` | major | pending |
