"""Dataset version numbers as they arrive in a path segment.

Role: `parse_version_number`, the only way a `{number}` path segment becomes a version number.
Used by: the domain barrel; through it `evals.evaluation.services.datasets`.
Depends on: the standard library only.
Key invariants: only the canonical decimal form of a published number is accepted — ASCII
  digits, no sign, no leading zero, no spaces, no exponent, no fraction, at most nine digits —
  so `0`, `-1`, `01`, `+1`, `1.0`, `1e0`, `" 1"`, `1_0` and fullwidth digits are all "no such
  version" (C-205). Nothing larger than 999,999,999 ever reaches SQL (an int4 column; the
  FIX-004 lesson). `int()` runs only after the pattern matched, never on raw input. Pure.
"""

import re

VERSION_NUMBER = re.compile(r"[1-9][0-9]{0,8}")


def parse_version_number(segment: str) -> int | None:
    """The version number a path segment names, or None when it names none."""
    if VERSION_NUMBER.fullmatch(segment) is None:
        return None
    return int(segment)
