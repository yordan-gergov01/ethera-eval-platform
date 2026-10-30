"""Tests of the coverage gates: each gate passes on a healthy report and fires on a bad one.

Role: proves scripts/coverage_gates.py enforces what docs/DECISIONS.md D-008 promises.
Used by: pytest.
Depends on: `scripts.coverage_gates` with hand-built coverage.py JSON reports.
Key invariants: every gate has a negative case — below threshold, a critical module missing
  from the report, a domain module below 90% hidden behind a well-tested one, a floor miss.
"""

from typing import Any

from scripts.coverage_gates import CRITICAL_PATHS, evaluate

FULL = {"covered_lines": 10, "num_statements": 10, "covered_branches": 2, "num_branches": 2}


def _file(covered: int, statements: int) -> dict[str, Any]:
    return {
        "summary": {
            "covered_lines": covered,
            "num_statements": statements,
            "covered_branches": 0,
            "num_branches": 0,
        }
    }


def _critical_files() -> dict[str, Any]:
    files = {}
    for prefix in CRITICAL_PATHS:
        path = prefix + "service.py" if prefix.endswith("/") else prefix
        files[path] = {"summary": FULL}
    return files


def _report(files: dict[str, Any], covered: int = 90, statements: int = 100) -> dict[str, Any]:
    return {"files": files, "totals": {"covered_lines": covered, "num_statements": statements}}


def test_evaluate_healthy_report_passes_every_gate() -> None:
    results = evaluate(_report(_critical_files()), floor=85.0)
    assert all(result.passed for result in results)


def test_critical_gate_below_100_fails() -> None:
    files = _critical_files()
    files["backend/core/tokens.py"] = _file(9, 10)
    result = evaluate(_report(files), floor=0)[0]
    assert not result.passed
    assert "backend/core/tokens.py" in result.detail


def test_critical_gate_missing_module_fails() -> None:
    files = _critical_files()
    del files["backend/core/security.py"]
    result = evaluate(_report(files), floor=0)[0]
    assert not result.passed
    assert "missing from report: backend/core/security.py" in result.detail


def test_critical_gate_windows_paths_are_normalised() -> None:
    files = {path.replace("/", "\\"): data for path, data in _critical_files().items()}
    assert evaluate(_report(files), floor=0)[0].passed


def test_domain_gate_is_per_module_and_fires_below_90() -> None:
    files = _critical_files() | {
        "evals/registry/domain/manifest.py": _file(100, 100),
        "evals/comparison/domain/gate.py": _file(8, 10),
    }
    results = {result.name: result for result in evaluate(_report(files), floor=0)}
    assert results["evals/registry/domain"].passed
    assert not results["evals/comparison/domain"].passed


def test_floor_gate_fails_below_the_floor() -> None:
    results = evaluate(_report(_critical_files(), covered=80, statements=100), floor=85.0)
    assert not results[-1].passed
