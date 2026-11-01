# Sealed oracle: 001-product-registry

The acceptance oracle for `contract.md` (approved, D-022), written by the `test-author`
agent BEFORE any implementation exists (Bible Phase 3) and reviewed with the `seal-oracle`
skill on 2026-10-31.

**These files never change by one byte.** `.claude/settings.json` denies editing them.
Implementers add their own test files beside them. The §6 helpers live in the implementer's
`ethera-eval-core/tests/integration/registry_fixtures.py`, which is not sealed.

**Model:** the test author ran on `opus` instead of `fable`. This is the slice 001 exception
recorded in D-011 (owner, 2026-10-31).

## Sealed files

| Sealed file | sha256 | Test cases | Fail reason today |
|---|---|---|---|
| `ethera-eval-core/tests/integration/registry/_contract_fixtures.py` | `5dfb615b294204d26ca082b1a5dad0bc6510a5d4cefc637e195d71a48dfc43cd` | — (helper door) | — |
| `ethera-eval-core/tests/integration/registry/_registry_oracle.py` | `35db0656bc8309b2177e1b2275c49943d3223cf50438c7c01b5671402d874c9d` | — (shared helpers) | — |
| `ethera-eval-core/tests/integration/registry/conftest.py` | `352284fc402d988469431f98f204892b4079204806401362489f368952bb4ddc` | — (`api` fixture) | — |
| `ethera-eval-core/tests/integration/registry/test_manifest_concurrency.py` | `ef45799b386a2092f849e4f7243daffdab07ca6a93bd0105563b386e38dbc180` | 3 | §6 `started_platform_app` not provided |
| `ethera-eval-core/tests/integration/registry/test_manifest_refusals.py` | `1838491fb705ea019299b48bb1675f1d7e0e3026c5f2cf94f6d6271f94e659c1` | 10 | same |
| `ethera-eval-core/tests/integration/registry/test_manifest_replace.py` | `cae8f138f2d7699d2d56b5fa93c676ffca6a442021e093f553291c17f02b075a` | 32 | same |
| `ethera-eval-core/tests/integration/registry/test_manifest_validation_document.py` | `5703c9d263f51b7dafe19c0bcdaf3e4aaf53d6c8772fe08b4c11ac27f0c484c5` | 73 | same |
| `ethera-eval-core/tests/integration/registry/test_manifest_validation_schema.py` | `33aeb8d8b032dbcf6f0ceb35fb9ff2eeb92cea6f318d7480ffc8788e2775dd2a` | 58 | same |
| `ethera-eval-core/tests/integration/registry/test_product_read.py` | `6d5ecc01130f037ae24f0e99929404c78ff77dc2398e5083bf1a14562092a68c` | 16 | same |
| `ethera-eval-core/tests/integration/registry/test_products_list.py` | `a8a37c688abb5d891341b550013144946a3294040bf86d0513da9b1d04988515` | 16 | same |
| `ethera-eval-core/tests/integration/registry/test_registry_audit.py` | `b160c1fcf53ada66521cf21f05ea9f9e5bbcf6bb35272efd82e18be52d327bf7` | 4 | same |
| `ethera-eval-core/tests/integration/registry/test_registry_never_log.py` | `d70cb8a9c48e0b32a0e4c1f566fbe0cbd74c6f09355b01355e99d5b0c7b11d12` | 2 | §6 `platform_app` not provided |
| `ethera-eval-core/tests/integration/registry/test_registry_seed.py` | `e2acb75ac282651502aebe6f1d4028cddf6ba87c62d8fa23bcb15ab69803bd8b` | 5 | 3 × `started_platform_app`, 2 × `platform_app` not provided |
| `ethera-eval-core/tests/integration/registry/test_registry_tenancy.py` | `8a02899deb9a0250aa16d6e98572d33799797303031b1782df016054003e29e7` | 5 | §6 `started_platform_app` not provided |

**Hashes** are of the files as stored in Git (LF line endings, `.gitattributes`), the bytes
a fresh clone has. Check with `sha256sum` after a checkout.

## Re-seal (owner, 2026-10-31, FIX-001)

One case in `test_manifest_replace.py` was defective. The `whitespace` parameter of
`test_equal_manifest_returns_the_current_version_unchanged` doubled every indent and so
produced text that is not YAML (PyYAML: `mapping values are not allowed here`); no correct
implementation could return 200 for it. With the owner's approval the test author replaced
only that expression with a whitespace-only variant that is valid YAML and loads to the same
Manifest (re-indented blocks, trailing spaces, blank lines). No other line of any sealed file
changed. The file's hash above is the re-sealed one; the original was
`5ae8c6d2247789dd6625cfa722caf2ba3701bd092faa2a66a7f028b3eeba4424`.

## Soundness review (seal-oracle, 2026-10-31)

- **Imports:** the oracle imports no `backend`, `evals`, `runner`, `demo_target` or
  `common_lib` code. The only dynamic import is `_contract_fixtures.py` loading the
  implementer's `tests.integration.registry_fixtures` (contract §6).
- **Lint and types:** `ruff format --check`, `ruff check` and `mypy` are clean on all 14
  files.
- **Today's run** (`REQUIRE_INTEGRATION=1 pytest tests/integration/registry`, against the
  real test PostgreSQL and RabbitMQ): 224 collected, 224 failed, 0 errors, 0 passed. 220
  fail with `contract §6 fixture not yet provided: started_platform_app` and 4 with
  `… platform_app`. Each is an explicit `pytest.fail` raised at use time, never a collection
  or import error.
- **Anti-vacuity (helpers present, feature absent):** the oracle was rerun against a simulated helper
  module. It started the real platform app, but the helpers wrote nothing and the registry
  routes were absent. Result: 224 failed, 0 passed (533 s). The failures are HTTP mismatches
  (mostly `404 == 422`, `404 == 201`, `404 == 200`), `NOT_FOUND` ≠ `PRODUCT_NOT_FOUND`, empty
  audit rows, and no single 201 under concurrency. No test passes vacuously.

## How each test fails once the §6 helpers exist but the feature does not

From the test author's map, checked in the simulated run above. "Generic 404" means the
platform's `{"status": 404, "code": "NOT_FOUND"}` for an unknown route.

| Tests | Expected failure | Anchor against a vacuous pass |
|---|---|---|
| list and read: token, shape, order, paging | generic 404 where 200 is expected | the admin or member first gets a 200 |
| read: not-found, off-pattern, equal 404 bodies | generic 404 on the anchor read; `NOT_FOUND` ≠ `PRODUCT_NOT_FOUND` | the caller's own Product answers 200 first |
| replace: versions, equality, response order, body shape, permission | generic 404 ≠ the expected 200/201/400/401/403/409/422 | a closing 201 or 200 on the same route |
| validation (document level and schema) | generic 404 ≠ `422 MANIFEST_INVALID` | the exact `errors` set |
| concurrency | all 404, so no single 201 | exactly one 201 |
| refusals change nothing | generic 404 on the seeded-state read | a closing 201 must change the snapshot |
| tenancy | generic 404 on the helper check through the API | arranged Products are seen by their member first |
| audit | 404 ≠ 201, or no rows | exact rows after a 201 |
| seed | 404 where 200 is expected; zero `manifest_created` rows | the exact demo document at version 1 |
| never-log | 404 ≠ 201 | the `manifest_replaced` / `manifest_refused` events must be present |

## Not sealed (underdetermined; from the test author)

1. Several document-level defects in one document: which one is reported (contract §3.3
   rule 1). Anchor plus alias is sealed only because every candidate gives the same pair.
2. Whether `unknown_key` looks inside an unknown key's value.
3. Rule 5 when an `allowed_providers` element is not a string (the wording admits two
   readings).
4. An empty or odd string inside `allowed_providers`: `invalid_value` or
   `unknown_provider`.
5. Whether the demo document ends with a newline. It is compared with `demo_document()`
   exactly, and with the contract literal after stripping trailing newlines.
6. The exact `client_ip` value. Only non-null and parseable as an IP are sealed, and not for
   `arrange_product` rows.
7. A 32,768-character `document` of multibyte characters. Only ASCII is sealed.
8. Concurrent equal and different documents on one `base_version`. Both orders are legal.
9. Log lines for 409, `VALIDATION_FAILED`, 400/401/403/404 and the equal-Manifest 200. Only
   marker absence is sealed.
10. `base_version` given as `"1"`, `true`, `1.5` or a huge integer.
11. Non-integer or repeated `limit`/`offset`.
12. Empty path segments and other routing edges.
13. On `GET`, whether 401 or the off-pattern 404 comes first. The contract orders the rows
    for `PUT` only.
14. The seed under a non-default `ADMIN_USERNAME`.
15. The sort order of `changed_sections`. In slice 001 only `bindings` can change.
16. YAML 1.1 tokens the contract does not list (`0o17`, `+1`, `-.inf`, `.NaN`, `0b101`,
    `Y`, `N`).
17. Whether the equal-Manifest 200 updates `changed_at`. It is sealed only through the
    unchanged read answers.
18. A `null` or boolean `role` combined with other bindings' duplicate checks.
