"""Mechanical guard: every Python file opens with the four-part header; test pointers resolve.

Role: enforces the Bible's docstring rule (.claude/rules/code-quality.md) for every Python file
  of ethera-eval-core, so the boundary signage cannot silently decay.
Used by: pytest (part of the normal suite, therefore the gate and CI).
Depends on: `ast` over the source tree; no application imports.
Key invariants: no exemptions (docs/DECISIONS.md D-009); the labels Role / Used by /
  Depends on / Key invariants appear in this order in the module docstring; every
  `test_<name>` mentioned in a header names a real test function or test module; the
  negative cases below prove the guard fires.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("backend", "common_lib", "runner", "evals", "demo_target", "migrations", "scripts")
LABELS = ("Role:", "Used by:", "Depends on:", "Key invariants:")
TEST_REFERENCE = re.compile(r"\btest_[a-z0-9_]+\b")


def python_files() -> list[Path]:
    roots = [ROOT / name for name in (*PACKAGES, "tests")]
    return sorted(
        path for root in roots if root.exists() for path in root.rglob("*.py") if path.is_file()
    )


def header_problems(source: str) -> list[str]:
    """The missing or out-of-order labels of a module docstring; empty when valid."""
    docstring = ast.get_docstring(ast.parse(source), clean=False)
    if not docstring:
        return ["no module docstring"]
    problems = []
    cursor = -1
    for label in LABELS:
        at = docstring.find(label)
        if at == -1:
            problems.append(f"missing {label!r}")
        elif at < cursor:
            problems.append(f"{label!r} out of order")
        else:
            cursor = at
    return problems


def known_test_names(files: list[Path]) -> set[str]:
    names = set()
    for path in files:
        if not path.is_relative_to(ROOT / "tests"):
            continue
        names.add(path.stem)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                names.add(node.name)
    return names


def unresolved_references(source: str, known: set[str]) -> list[str]:
    docstring = ast.get_docstring(ast.parse(source), clean=False) or ""
    return sorted({ref for ref in TEST_REFERENCE.findall(docstring) if ref not in known})


def test_finds_the_source_files() -> None:
    assert len(python_files()) > 100


def test_every_python_file_has_the_four_part_header() -> None:
    offenders = [
        f"{path.relative_to(ROOT).as_posix()}: {', '.join(problems)}"
        for path in python_files()
        if (problems := header_problems(path.read_text(encoding="utf-8")))
    ]
    assert offenders == []


def test_every_test_reference_in_a_header_resolves() -> None:
    files = python_files()
    known = known_test_names(files)
    offenders = [
        f"{path.relative_to(ROOT).as_posix()}: {', '.join(refs)}"
        for path in files
        if (refs := unresolved_references(path.read_text(encoding="utf-8"), known))
    ]
    assert offenders == []


def test_header_problems_fires_without_a_docstring() -> None:
    assert header_problems("import os\n") == ["no module docstring"]


def test_header_problems_fires_on_missing_or_misordered_labels() -> None:
    assert header_problems('"""x\n\nRole: a\nUsed by: b\nKey invariants: c\n"""') == [
        "missing 'Depends on:'"
    ]
    assert header_problems(
        '"""x\n\nUsed by: b\nRole: a\nDepends on: c\nKey invariants: d\n"""'
    ) == ["'Used by:' out of order"]


def test_header_problems_accepts_a_complete_header() -> None:
    source = '"""x\n\nRole: a\nUsed by: b\nDepends on: c\nKey invariants: d\n"""'
    assert header_problems(source) == []


def test_unresolved_references_fires_on_a_vanished_test() -> None:
    source = '"""x\n\nKey invariants: sealed by test_gone_forever and test_kept.\n"""'
    assert unresolved_references(source, {"test_kept"}) == ["test_gone_forever"]
