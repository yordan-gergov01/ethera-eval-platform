"""Mechanical guard: file and function length caps, with a ratchet for today's offenders.

Role: enforces the Bible's size rule (.claude/rules/code-quality.md): files at most 600 lines,
  functions at most 100 lines.
Used by: pytest (part of the normal suite, therefore the gate and CI).
Depends on: `ast` over the source tree; no application imports.
Key invariants: an offender pinned below may shrink but never grow, and a new offender fails;
  an entry that is no longer an offender must be removed from the pin list (the ratchet only
  tightens); the negative cases below prove the guard fires (docs/DECISIONS.md D-009).
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("backend", "common_lib", "runner", "evals", "demo_target", "migrations", "scripts")
FILE_CAP = 600
FUNCTION_CAP = 100

# Offenders that existed when the guard was introduced (template code), pinned at their size.
PINNED_FILES: dict[str, int] = {}
PINNED_FUNCTIONS: dict[str, int] = {
    "backend/main.py::create_app": 114,
}


def python_files() -> list[Path]:
    roots = [ROOT / name for name in (*PACKAGES, "tests")]
    return sorted(path for root in roots if root.exists() for path in root.rglob("*.py"))


def file_sizes(files: list[Path]) -> dict[str, int]:
    return {
        path.relative_to(ROOT).as_posix(): len(path.read_text(encoding="utf-8").splitlines())
        for path in files
    }


def function_sizes(name: str, source: str) -> dict[str, int]:
    sizes = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.end_lineno:
            sizes[f"{name}::{node.name}"] = node.end_lineno - node.lineno + 1
    return sizes


def ratchet_violations(sizes: dict[str, int], cap: int, pinned: dict[str, int]) -> list[str]:
    """New offenders, pinned offenders that grew, and pins that are no longer needed."""
    problems = []
    for key, size in sorted(sizes.items()):
        if size > cap and key not in pinned:
            problems.append(f"{key}: {size} lines > {cap}")
        elif key in pinned and size > pinned[key]:
            problems.append(f"{key}: grew from {pinned[key]} to {size} lines")
    for key, size in sorted(pinned.items()):
        if sizes.get(key, 0) <= cap:
            problems.append(f"{key}: no longer above {cap}; remove its pin ({size})")
    return problems


def test_files_stay_within_the_cap() -> None:
    assert ratchet_violations(file_sizes(python_files()), FILE_CAP, PINNED_FILES) == []


def test_functions_stay_within_the_cap() -> None:
    sizes: dict[str, int] = {}
    for path in python_files():
        name = path.relative_to(ROOT).as_posix()
        sizes |= function_sizes(name, path.read_text(encoding="utf-8"))
    assert ratchet_violations(sizes, FUNCTION_CAP, PINNED_FUNCTIONS) == []


def test_ratchet_fires_on_a_new_offender() -> None:
    assert ratchet_violations({"a.py": 601}, FILE_CAP, {}) == ["a.py: 601 lines > 600"]


def test_ratchet_fires_when_a_pinned_offender_grows() -> None:
    assert ratchet_violations({"a.py": 650}, FILE_CAP, {"a.py": 640}) == [
        "a.py: grew from 640 to 650 lines"
    ]


def test_ratchet_allows_a_pinned_offender_to_shrink() -> None:
    assert ratchet_violations({"a.py": 620}, FILE_CAP, {"a.py": 640}) == []


def test_ratchet_demands_removing_a_pin_that_is_no_longer_needed() -> None:
    assert ratchet_violations({"a.py": 500}, FILE_CAP, {"a.py": 640}) == [
        "a.py: no longer above 600; remove its pin (640)"
    ]


def test_function_sizes_measures_every_function() -> None:
    source = "def f():\n    pass\n\n\nasync def g():\n    x = 1\n    return x\n"
    assert function_sizes("m.py", source) == {"m.py::f": 2, "m.py::g": 3}
