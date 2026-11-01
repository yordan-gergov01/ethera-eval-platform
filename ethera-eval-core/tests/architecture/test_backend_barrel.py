"""The core's barrel exports nothing the domain does not use (no dead seams).

Role: scans `backend/__init__.py` and every Python file under `evals/` with `ast`: each name in
  the barrel's `__all__` must be imported from `backend` somewhere in `evals/`.
Used by: pytest (architecture guard).
Depends on: the standard library (`ast`, `pathlib`); the source tree, read as text. No services.
Key invariants: `test_backend_barrel_exports_only_what_evals_imports` reads the barrel's
  `__all__` as written, without importing it, and counts only `from backend import ...` in
  `evals/` (the one door the import contracts allow); the negative case proves an unused export
  would be caught.
"""

import ast
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2]
BARREL = CORE_ROOT / "backend" / "__init__.py"


def barrel_exports(source: str) -> set[str]:
    """The string entries of the module's `__all__` list."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            assert isinstance(node.value, ast.List | ast.Tuple)
            return {
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
    raise AssertionError("the barrel has no __all__")


def names_imported_from_backend(sources: list[str]) -> set[str]:
    """Every name imported with `from backend import ...` in the given sources."""
    names: set[str] = set()
    for source in sources:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module == "backend" and node.level == 0:
                names.update(alias.name for alias in node.names)
    return names


def unused_exports(barrel_source: str, domain_sources: list[str]) -> list[str]:
    return sorted(barrel_exports(barrel_source) - names_imported_from_backend(domain_sources))


def test_backend_barrel_exports_only_what_evals_imports() -> None:
    domain = [path.read_text(encoding="utf-8") for path in (CORE_ROOT / "evals").rglob("*.py")]
    barrel = BARREL.read_text(encoding="utf-8")

    assert barrel_exports(barrel)
    assert unused_exports(barrel, domain) == []


def test_unused_export_is_detected() -> None:
    barrel = '__all__ = ["create_app", "Unused"]\n'
    domain = ["from backend import create_app\n"]

    assert unused_exports(barrel, domain) == ["Unused"]
