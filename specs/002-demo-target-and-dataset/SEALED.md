# Sealed oracle: 002-demo-target-and-dataset

The acceptance oracle for `contract.md` (approved, D-025), written by the `test-author` agent
BEFORE any implementation exists (Bible Phase 3) and reviewed with the `seal-oracle` skill on
2026-11-01.

**These files never change by one byte.** `.claude/settings.json` denies editing them.
Implementers add their own test files beside them. The §6 helpers live in the implementer's
`ethera-eval-core/tests/integration/evaluation_fixtures.py`, which is not sealed; the slice 001
helpers are reached through the sealed 001 door (`tests/integration/registry/_contract_fixtures.py`).

**Model:** the test author ran on `opus` instead of `fable` (the D-011 exception).

## Sealed files

| Sealed file | sha256 | Test cases | Fail reason today |
|---|---|---|---|
| `ethera-eval-core/tests/integration/evaluation/_contract_fixtures.py` | `44664722ebf377aefef4631fb30863b9b79b905fe3efbde59caf4bff9100b1c0` | — (helper door) | — |
| `ethera-eval-core/tests/integration/evaluation/_evaluation_oracle.py` | `8423413f58f50d98c8ba64d11499fa40739504e9f3a39b5008f08530677e83c4` | — (tables, pass rule, shapes) | — |
| `ethera-eval-core/tests/integration/evaluation/conftest.py` | `303d4f94b495ba4aaa990dabf3cd6552b643265bdc7e8b7fe6864f13a387c9dc` | — (`api` fixture) | — |
| `ethera-eval-core/tests/integration/evaluation/test_dataset_seed.py` | `3b19a8cedd217f7e02ae3b455e138c975b3609319fc0ba301ae5c1db897374ca` | 5 | the platform starts (001 helpers exist); the Dataset routes answer the framework's 404 `NOT_FOUND` |
| `ethera-eval-core/tests/integration/evaluation/test_dataset_versions.py` | `528882b4d96cfb25689a82a299bec293274883e5d2adec6774db2c16ef79ca80` | 7 | route 404 at the 200 anchor; one test `NOT_FOUND` ≠ `DATASET_NOT_FOUND`; one §6 `arrange_dataset_version` missing |
| `ethera-eval-core/tests/integration/evaluation/test_dataset_tenancy.py` | `ba017103b4f7dab9feea36b5ec3def50357c78da78988e91998c5abf438f9070` | 5 | §6 `arrange_dataset_version` missing |
| `ethera-eval-core/tests/integration/evaluation/test_demo_target_chat.py` | `f51dbf707e7ca35888d1af4ad691911d16b80458fa998ea9c1139841f58812d3` | 24 | §6 `demo_target_client` missing |
| `ethera-eval-core/tests/integration/evaluation/test_scenario_matrix.py` | `d8d2e094b15fc56f19c0562eef886fc82f7698a3666e614bfa4fe2762ce96d32` | 11 | route 404 reading the seed through §2.2 |
| `ethera-eval-core/tests/integration/evaluation/test_evaluation_never_log.py` | `e109258f8c611ad5aa3f136cb54ae76ad1943c0b3689eead44d3d7028fa3b3ac` | 2 | §6 `arrange_dataset_version` / `demo_target_logs` missing |

**Hashes** are of the files as stored in Git (LF line endings, `.gitattributes`). Check with
`sha256sum` after a checkout.

## Soundness review (seal-oracle, 2026-11-01)

- **Imports:** no `backend`, `evals`, `runner`, `demo_target` or `common_lib` import. The only
  dynamic import is the door to `tests.integration.evaluation_fixtures` (contract §6).
- **Lint and types:** `ruff format --check`, `ruff check` and `mypy` clean on all 9 files;
  `pytest tests/architecture` passes (headers, lengths).
- **Today's run** (`REQUIRE_INTEGRATION=1 pytest tests/integration/evaluation`, real test
  PostgreSQL and RabbitMQ): 54 collected, 54 failed, 0 errors, 0 passed. Every failure is an
  explicit `pytest.fail` for a missing §6 helper or an HTTP mismatch at a 200 anchor, never a
  collection, import or fixture error.
- **The matrix is the contract's:** `MATRIX` in `test_scenario_matrix.py` equals the ✓/✗ table
  of contract §3.4, cell for cell (checked by parsing both), with columns B, PR, Ret, Rel, Exp.
  The §3.5 Golden table in `_evaluation_oracle.py` was extracted from the contract and checked
  back against it. The matrix reads the seeded questions through §2.2, so a seed and a
  behaviour that drift apart fail.
- **Anti-vacuity:** every refusal is believed only after a 200 on the caller's own resource;
  the no-audit-row test reads the Dataset summary (200) first; never-log tests require the
  marker to appear in a 200 body and a `/dataset` line in the capture.

## Contract erratum found while sealing

Contract §3.2 and §7 say version 1's body is equal before and after version 2 is published;
§3.2 also says `is_current` is true only for the highest number, so `is_current` must change.
The oracle seals body equality **except `is_current`**, plus the flip to `false`. The contract
text was corrected to say so (owner, 2026-11-01, at the seal commit; D-025).

## Sealed beyond the literal §7 list

C-209 usage equal across models and the 2.5 cost ratio for all 19 questions; any non-null fact
`source` in `retrieved_doc_ids`; configuration values matched exactly (case and whitespace
variants are unknown); `/chat` answers `application/json` with a non-empty `answer`, no
duplicate document IDs, facts with exactly `source` and `statement`; 2,000 `é` admitted and
2,001 refused; concurrent and sequential bodies equal, and a `422` consumes nothing; each
medium call's wall time is below its `latency_ms`; extra version segments (`+1`, `1e0`, `%201`,
fullwidth `１`, `02`, `3`) refused; the Product gate before the version check, including
uppercase and 65-character identifiers; arranging a version writes no audit row and survives a
restart; R1, R3/R4 as conditionals, R4's PR = B for sourced Goldens, R5 and R6.

## Not sealed (underdetermined; from the test author)

1. 403 on both endpoints (both roles hold `products:read`).
2. The literal `published_at`; only the UTC offset and ascending order are sealed.
3. The demo target's 422 body shape; only the status and the absence of `answer`/`latency_ms`.
4. Whitespace-only or astral-plane questions (code points vs UTF-16 units).
5. R2 as such (only its matrix cells).
6. R4 for `answer` text, `usage` and `latency_ms` between instruction sets.
7. Whether the demo target logs anything at all: if it logs nothing, its never-log test passes
   trivially (the implementer's own test must prove the one request line of R-206).
8. Ordering of `facts_used`; `answer` and `statement` texts.
9. Concurrent `arrange_dataset_version` calls.
10. `arrange_dataset_version` with an empty Golden list.
11. `versions/abc` on a member's Product without a Dataset (`DATASET_NOT_FOUND` or
    `DATASET_VERSION_NOT_FOUND`).
12. Pricing string digits (`"0.20"` vs `"0.2"`): Decimal equality only.
13. Usage equality across instruction sets or retrieval modes.
14. Behaviour on refused configurations beyond "entering raises".
