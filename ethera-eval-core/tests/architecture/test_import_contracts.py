"""The import-linter contracts in pyproject.toml hold for the whole code base.

Role: runs the `[tool.importlinter]` contracts (for example: the backend and the runner do not
  import each other) as a test, so a forbidden import fails the suite. The negative case
  `test_platform_import_of_the_demo_target_breaks_its_contract` plants `import demo_target` in
  each source package of that contract, in a throwaway tree, and proves the real contract fires.
Used by: pytest (architecture guard).
Depends on: import-linter's `lint_imports` over pyproject.toml, and its `lint-imports` command
  in a subprocess for the negative case; the local `_keep_loggers_enabled` fixture. No services.
Key invariants: import-linter runs without its cache (`no_cache=True`); loggers that its
  `dictConfig` call disables are re-enabled afterwards, so later tests still see log output.
  The negative case reads the contract from pyproject.toml by name, never a copy, and runs in a
  subprocess whose PYTHONPATH puts the throwaway tree first, so the installed packages are not
  the ones analysed; a clean throwaway tree must pass, so the failure is the planted import's.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest
from importlinter.cli import EXIT_STATUS_SUCCESS, lint_imports

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


@pytest.fixture
def _keep_loggers_enabled() -> Iterator[None]:
    """Undo the side effect of import-linter's logging setup on existing loggers.

    It calls `logging.config.dictConfig`, which disables every logger that already
    exists (`disable_existing_loggers` defaults to true). Later tests would then see
    no output from loggers such as uvicorn's.
    """
    enabled = [
        logger
        for logger in logging.root.manager.loggerDict.values()
        if isinstance(logger, logging.Logger) and not logger.disabled
    ]
    yield
    for logger in enabled:
        logger.disabled = False


@pytest.mark.usefixtures("_keep_loggers_enabled")
def test_import_contracts_hold() -> None:
    assert lint_imports(config_filename=str(PYPROJECT), no_cache=True) == EXIT_STATUS_SUCCESS


DEMO_TARGET_CONTRACT = "The platform never imports the demo target"
PLATFORM_PACKAGES = ("backend", "runner", "common_lib", "evals", "migrations", "scripts")


def _contract_modules(name: str) -> tuple[list[str], list[str]]:
    """The source and forbidden modules of the pyproject.toml contract called `name`."""
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["importlinter"]
    contract = next(c for c in config["contracts"] if c["name"] == name)
    return list(contract["source_modules"]), list(contract["forbidden_modules"])


def _lint_throwaway_tree(root: Path, planted_in: str | None) -> int:
    """`lint-imports` over stub packages under `root` with the real demo-target contract."""
    sources, forbidden = _contract_modules(DEMO_TARGET_CONTRACT)
    packages = [*PLATFORM_PACKAGES, *forbidden]
    for package in packages:
        (root / package).mkdir()
        (root / package / "__init__.py").write_text("", encoding="utf-8")
    if planted_in is not None:
        (root / planted_in / "planted.py").write_text("import demo_target\n", encoding="utf-8")
    config = [
        "[tool.importlinter]",
        f"root_packages = {json.dumps(packages)}",
        "[[tool.importlinter.contracts]]",
        f"name = {json.dumps(DEMO_TARGET_CONTRACT)}",
        'type = "forbidden"',
        f"source_modules = {json.dumps(sources)}",
        f"forbidden_modules = {json.dumps(forbidden)}",
    ]
    (root / "pyproject.toml").write_text("\n".join(config) + "\n", encoding="utf-8")
    command = shutil.which("lint-imports", path=str(Path(sys.executable).parent))
    assert command is not None
    return subprocess.run(  # noqa: S603 - our own venv's lint-imports on a throwaway tree
        [command, "--config", str(root / "pyproject.toml"), "--no-cache"],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        check=False,
    ).returncode


def test_platform_without_a_demo_target_import_keeps_its_contract(tmp_path: Path) -> None:
    assert _lint_throwaway_tree(tmp_path, planted_in=None) == EXIT_STATUS_SUCCESS


@pytest.mark.parametrize("package", PLATFORM_PACKAGES)
def test_platform_import_of_the_demo_target_breaks_its_contract(
    tmp_path: Path, package: str
) -> None:
    assert _lint_throwaway_tree(tmp_path, planted_in=package) != EXIT_STATUS_SUCCESS
