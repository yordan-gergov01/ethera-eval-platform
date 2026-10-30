"""The coverage gates, run as a separate pass over coverage.py's JSON report.

Role: enforces the Bible's coverage floors: 100% on auth, authorization, tenancy and audit
  modules; >= 90% on every `evals/*/domain` package; a repo-wide floor read from
  `.coverage-floor` that may only rise. Usage:
  `python scripts/coverage_gates.py coverage.json [--raise-floor]`.
Used by: `.github/workflows/core.yml`, the `full-gate` skill; tested by
  tests/unit/scripts/test_coverage_gates.py.
Depends on: the standard library; a report from `pytest --cov --cov-report=json:<path>`
  (line + branch coverage, configured in pyproject.toml).
Key invariants: a listed critical path that is missing from the report FAILS (a deleted or
  renamed auth module must not silently leave the gate); the domain gate applies per module
  package, so one well-tested module cannot hide another; `--raise-floor` only ever raises
  the floor. New tenancy and audit modules are appended to CRITICAL_PATHS when they exist
  (docs/DECISIONS.md D-008, D-010).
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CRITICAL_THRESHOLD = 100.0
DOMAIN_THRESHOLD = 90.0
FLOOR_FILE = Path(__file__).resolve().parents[1] / ".coverage-floor"

# Authentication and authorization; tenancy and audit modules join when they exist.
CRITICAL_PATHS: tuple[str, ...] = (
    "backend/services/auth/",
    "backend/core/security.py",
    "backend/core/tokens.py",
    "backend/api/dependencies/auth.py",
    "backend/api/dependencies/permissions.py",
    "common_lib/permissions.py",
)


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    percent: float | None
    required: float
    passed: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class _Counts:
    covered: int = 0
    total: int = 0

    def __add__(self, other: "_Counts") -> "_Counts":
        return _Counts(self.covered + other.covered, self.total + other.total)

    @property
    def percent(self) -> float:
        return 100.0 if self.total == 0 else 100.0 * self.covered / self.total


def _counts(summary: Mapping[str, Any]) -> _Counts:
    """Statements plus branches, the same measure coverage.py reports as the total."""
    covered = summary["covered_lines"] + summary.get("covered_branches", 0)
    total = summary["num_statements"] + summary.get("num_branches", 0)
    return _Counts(covered, total)


def _normalise(files: Mapping[str, Any]) -> dict[str, _Counts]:
    return {path.replace("\\", "/"): _counts(data["summary"]) for path, data in files.items()}


def critical_gate(files: Mapping[str, _Counts]) -> GateResult:
    total = _Counts()
    missing = []
    for prefix in CRITICAL_PATHS:
        matched = [counts for path, counts in files.items() if path.startswith(prefix)]
        if not matched:
            missing.append(prefix)
        for counts in matched:
            total = total + counts
    under = sorted(
        path
        for path, counts in files.items()
        if any(path.startswith(p) for p in CRITICAL_PATHS) and counts.percent < CRITICAL_THRESHOLD
    )
    detail = "; ".join(
        part
        for part in (
            f"missing from report: {', '.join(missing)}" if missing else "",
            f"below 100%: {', '.join(under)}" if under else "",
        )
        if part
    )
    passed = not missing and not under
    return GateResult("auth/authz/tenancy/audit", total.percent, CRITICAL_THRESHOLD, passed, detail)


def domain_gates(files: Mapping[str, _Counts]) -> list[GateResult]:
    per_module: dict[str, _Counts] = {}
    for path, counts in files.items():
        parts = path.split("/")
        if len(parts) > 3 and parts[0] == "evals" and parts[2] == "domain":
            key = f"evals/{parts[1]}/domain"
            per_module[key] = per_module.get(key, _Counts()) + counts
    return [
        GateResult(key, counts.percent, DOMAIN_THRESHOLD, counts.percent >= DOMAIN_THRESHOLD)
        for key, counts in sorted(per_module.items())
    ]


def floor_gate(total_percent: float, floor: float) -> GateResult:
    return GateResult("repo-wide", total_percent, floor, total_percent >= floor)


def read_floor(path: Path = FLOOR_FILE) -> float:
    return float(path.read_text(encoding="utf-8").strip())


def evaluate(report: Mapping[str, Any], floor: float) -> list[GateResult]:
    files = _normalise(report["files"])
    totals = report["totals"]
    total_percent = _counts(totals).percent
    return [critical_gate(files), *domain_gates(files), floor_gate(total_percent, floor)]


def _print(results: Sequence[GateResult]) -> None:
    for result in results:
        mark = "PASS" if result.passed else "FAIL"
        percent = "n/a" if result.percent is None else f"{result.percent:.2f}%"
        line = f"{mark}  {result.name}: {percent} (required {result.required:.2f}%)"
        print(line + (f" — {result.detail}" if result.detail else ""))  # noqa: T201


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path)
    parser.add_argument("--raise-floor", action="store_true", help="raise the floor, never lower")
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    floor = read_floor()
    results = evaluate(report, floor)
    _print(results)
    if args.raise_floor:
        achieved = int(_counts(report["totals"]).percent * 100) / 100
        if achieved > floor:
            FLOOR_FILE.write_text(f"{achieved:.2f}\n", encoding="utf-8")
            print(f"floor raised {floor:.2f} -> {achieved:.2f}")  # noqa: T201
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
