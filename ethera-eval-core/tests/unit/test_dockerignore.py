"""Every path a Dockerfile copies from the build context survives `.dockerignore`.

Role: pins the build context against the Dockerfiles: `.dockerignore` excludes everything
  (`*`) and re-includes what the images need, so a directory the Dockerfiles copy but the
  allowlist forgets breaks `docker compose build` (FIX-006: `evals/` was missing, so the
  backend image could not be built).
Used by: pytest (unit).
Depends on: `.dockerignore`, `backend/Dockerfile` and `runner/Dockerfile` at the
  ethera-eval-core root (all three are in the test image); no services.
Key invariants: `test_every_copied_path_is_in_the_build_context` reads the real files; the
  matcher understands only the allowlist shape this repository uses (`*` then `!path` lines),
  and refuses any other pattern rather than guessing.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILES = ("backend/Dockerfile", "runner/Dockerfile")


def allowlist(dockerignore: str) -> set[str]:
    """The re-included paths of an exclude-everything `.dockerignore`, without trailing `/`."""
    lines = [line.strip() for line in dockerignore.splitlines()]
    patterns = [line for line in lines if line and not line.startswith("#")]
    if not patterns or patterns[0] != "*":
        raise ValueError("expected an allowlist that starts by excluding everything ('*')")
    included: set[str] = set()
    for pattern in patterns[1:]:
        if pattern.startswith("!"):
            included.add(pattern[1:].rstrip("/"))
        elif not pattern.startswith("**/"):
            raise ValueError(f"unsupported .dockerignore pattern: {pattern}")
    return included


def copied_sources(dockerfile: str) -> list[str]:
    """The build-context sources of every `COPY` line (stage copies `--from=` excluded)."""
    sources: list[str] = []
    for line in dockerfile.splitlines():
        words = line.split()
        if not words or words[0] != "COPY" or any(w.startswith("--from=") for w in words):
            continue
        sources.extend(word.rstrip("/") for word in words[1:-1] if not word.startswith("--"))
    return sources


def is_included(source: str, included: set[str]) -> bool:
    parts = source.split("/")
    return any("/".join(parts[: i + 1]) in included for i in range(len(parts)))


def test_every_copied_path_is_in_the_build_context() -> None:
    included = allowlist((ROOT / ".dockerignore").read_text(encoding="utf-8"))
    sources = {
        source
        for name in DOCKERFILES
        for source in copied_sources((ROOT / name).read_text(encoding="utf-8"))
    }

    assert sources, "no COPY sources found: the scan proves nothing"
    assert not {source for source in sources if not is_included(source, included)}


def test_a_forgotten_directory_is_reported() -> None:
    included = allowlist("*\n!backend/\n**/__pycache__/\n")

    assert is_included("backend", included)
    assert is_included("requirements/backend.txt", allowlist("*\n!requirements/\n"))
    assert not is_included("evals", included)
    assert copied_sources("COPY --from=deps /opt/venv /opt/venv\nCOPY evals ./evals\n") == ["evals"]


def test_an_unsupported_pattern_is_refused() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        allowlist("*\n!backend/\nsecrets.txt\n")
