"""Stop hook: fast checks for what changed, before Claude ends its turn.

Role: catches lint/format/type breakage in changed files cheaply at every stop; the full
  gate runs through the `full-gate` skill, never from a hook.
Used by: `.claude/settings.json` (Stop).
Depends on: git, `ethera-eval-core/.venv` (ruff), `ethera-eval-web/node_modules`
  (prettier, eslint); standard library only for itself.
Key invariants: exit 2 (with the failures on stderr) is the only blocking outcome; when
  `stop_hook_active` is true the hook reports nothing and exits 0, so a failing check can
  never trap a session in a loop. Missing tools are skipped, never treated as failures.
  Checks only changed files (git status), so it stays fast.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "ethera-eval-core"
WEB = ROOT / "ethera-eval-web"
WEB_SUFFIXES = (".ts", ".tsx")
TIMEOUT_SECONDS = 120


def _changed_files() -> list[Path]:
    result = subprocess.run(  # noqa: S603
        ["git", "status", "--porcelain", "--untracked-files=all"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    files = []
    for line in result.stdout.splitlines():
        name = line[3:].split(" -> ")[-1].strip().strip('"')
        path = ROOT / name
        if path.is_file():
            files.append(path)
    return files


def _first_existing(*candidates: Path) -> Path | None:
    return next((c for c in candidates if c.exists()), None)


def _run(label: str, args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(  # noqa: S603
            args, cwd=cwd, capture_output=True, text=True, check=False, timeout=TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0:
        return None
    output = (result.stdout + result.stderr).strip().splitlines()[-25:]
    return f"[{label}]\n" + "\n".join(output)


def _core_checks(files: list[Path]) -> list[str]:
    py = [
        str(f.relative_to(CORE))
        for f in files
        if f.suffix == ".py" and f.is_relative_to(CORE) and ".venv" not in f.parts
    ]
    ruff = _first_existing(CORE / ".venv/Scripts/ruff.exe", CORE / ".venv/bin/ruff")
    if not py or ruff is None:
        return []
    failures = [
        _run("ruff format", [str(ruff), "format", "--check", *py], CORE),
        _run("ruff check", [str(ruff), "check", *py], CORE),
    ]
    return [f for f in failures if f]


def _web_checks(files: list[Path]) -> list[str]:
    ts = [
        str(f.relative_to(WEB))
        for f in files
        if f.suffix in WEB_SUFFIXES and f.is_relative_to(WEB) and "node_modules" not in f.parts
    ]
    bin_dir = WEB / "node_modules/.bin"
    prettier = _first_existing(bin_dir / "prettier.cmd", bin_dir / "prettier")
    eslint = _first_existing(bin_dir / "eslint.cmd", bin_dir / "eslint")
    if not ts or prettier is None or eslint is None:
        return []
    failures = [
        _run("prettier", [str(prettier), "--check", *ts], WEB),
        # Explicitly passed files that ESLint ignores (schema.gen.ts) must not count as warnings.
        _run("eslint", [str(eslint), "--max-warnings=0", "--no-warn-ignored", *ts], WEB),
    ]
    return [f for f in failures if f]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    if event.get("stop_hook_active"):
        return 0
    files = _changed_files()
    failures = _core_checks(files) + _web_checks(files)
    if not failures:
        return 0
    print("Fast checks failed on changed files; fix them before stopping:", file=sys.stderr)
    print("\n\n".join(failures), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
