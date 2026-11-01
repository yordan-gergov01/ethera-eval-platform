"""Product identifiers: the slug rule for `client_id` and `project_id`.

Role: `is_identifier`, the identifier pattern of contract §2 (PP-013, INV-REG-13, C-1).
Used by: `evals.registry.domain.manifest` (the `product` section), the domain barrel; through it
  `evals.registry.services` (path segments are checked before any lookup).
Depends on: the standard library only.
Key invariants: 1 to 64 characters of lower-case letters, digits and `-`, with no leading or
  trailing `-`; the whole string must match (`fullmatch`, so a trailing newline never slips
  through). An identifier that breaks the rule is indistinguishable from a missing Product on
  the read and write paths (INV-REG-10). Pure.
"""

import re

IDENTIFIER_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")


def is_identifier(value: str) -> bool:
    """Whether `value` is a valid `client_id` or `project_id`."""
    return IDENTIFIER_PATTERN.fullmatch(value) is not None
