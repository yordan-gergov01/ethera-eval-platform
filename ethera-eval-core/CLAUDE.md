# ethera-eval-core — what differs here

The repository `CLAUDE.md` and `.claude/rules/` apply in full. Template conventions:
`../docs/reference/TEMPLATE_CONVENTIONS.md`; the template's own decisions (history):
`docs/DECISIONS.md`.

- **Venv:** `uv venv --python 3.12 .venv`, `uv pip install --require-hashes -r
  requirements/dev.txt`, `uv pip install -e . --no-deps`, then `source .venv/Scripts/activate`
  (Windows Git Bash) or `.venv/bin/activate`.
- **Checks:** `ruff format --check . && ruff check . && mypy && lint-imports`.
- **Tests:** `docker compose -f docker-compose.test.yml -p ethera_eval_core_test up -d --wait
  postgres rabbitmq`, then `REQUIRE_INTEGRATION=1 pytest`. Never two suite runs against the
  test stack at once. Coverage gates: `pytest --cov --cov-report=json:coverage.json` then
  `python scripts/coverage_gates.py coverage.json`.
- **Entry points:** production app `evals.app:create_app` (core + mounted modules); core alone
  `backend.main:create_app`. `backend` never imports `evals`; `evals` reaches the core only
  through the `backend` barrel (`backend/__init__.py`, append-only).
- **Modules:** `evals/<module>/` created only by the `add-module` skill; one Tortoise app label
  and migrations package each (D-007); registered by appending to `evals/MODULES.py`.
  `tortoise makemigrations` reads `evals.migration_cli.TORTOISE_ORM`.
- **Messaging:** publisher, consumers and runner worker are payload-generic and unwired until
  slice 003 (D-006); test payloads `Ping`/`Pong` live in `tests/job_payloads.py`.
- **Guards** (all in the normal suite): `tests/architecture/` (import contracts, headers, file
  and function length ratchet, registry completeness) and `tests/integration/`
  (`test_boot_without_evals.py`, `test_never_log.py`).
- **Line endings:** LF everywhere (`.gitattributes`); a CRLF shell script breaks the broker's
  entrypoint.
