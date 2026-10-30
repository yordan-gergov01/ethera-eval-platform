"""PostToolUse hook: format the file Claude just edited.

Role: keeps every edited file formatted with the project's own formatter, so diffs never
  carry formatting noise.
Used by: `.claude/settings.json` (PostToolUse, matcher `Edit|Write`).
Depends on: `ethera-eval-core/.venv` (ruff) and `ethera-eval-web/node_modules` (prettier);
  standard library only for itself.
Key invariants: never blocks and never fails the edit — every problem exits 0 silently
  (PostToolUse cannot undo a tool call anyway). Files outside the two projects and generated
  files are left untouched.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "ethera-eval-core"
WEB = ROOT / "ethera-eval-web"
PRETTIER_SUFFIXES = {".ts", ".tsx", ".js", ".mjs", ".css", ".json", ".md", ".yml", ".yaml"}
SKIP_NAMES = {"schema.gen.ts", "openapi.json", "package-lock.json"}


def _first_existing(*candidates: Path) -> Path | None:
    return next((c for c in candidates if c.exists()), None)


def _command_for(path: Path) -> tuple[list[str], Path] | None:
    if path.name in SKIP_NAMES:
        return None
    if path.is_relative_to(CORE) and path.suffix == ".py" and ".venv" not in path.parts:
        ruff = _first_existing(CORE / ".venv/Scripts/ruff.exe", CORE / ".venv/bin/ruff")
        return ([str(ruff), "format", "--quiet", str(path)], CORE) if ruff else None
    if path.is_relative_to(WEB) and path.suffix in PRETTIER_SUFFIXES:
        if "node_modules" in path.parts:
            return None
        prettier = _first_existing(
            WEB / "node_modules/.bin/prettier.cmd", WEB / "node_modules/.bin/prettier"
        )
        return ([str(prettier), "--write", "--log-level=silent", str(path)], WEB) if prettier else None
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
        path = Path(event["tool_input"]["file_path"]).resolve()
    except (ValueError, KeyError, TypeError):
        return 0
    command = _command_for(path)
    if command is not None:
        args, cwd = command
        try:
            subprocess.run(args, cwd=cwd, check=False, capture_output=True, timeout=60)  # noqa: S603
        except (OSError, subprocess.TimeoutExpired):
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
