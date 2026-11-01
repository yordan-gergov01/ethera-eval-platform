"""Model providers and their full-model-ID rules, kept as data.

Role: `FULL_MODEL_ID_RULES` (per provider, the pattern a full model ID matches), `KnownProvider`
  (the same provider names as a type), `is_known_provider`
  and `is_full_model_id` — how an alias is told apart from a full model ID (INV-REG-01,
  INV-REG-04, D-017 Fork B2, C-9).
Used by: `evals.registry.domain.manifest`; the domain barrel (`KnownProvider`), and through it
  `evals.registry.api.schemas`.
Depends on: the standard library only.
Key invariants: a provider is known iff it has a rule; slice 001 knows only `mock`, whose full
  IDs are `mock-<family>-<size>-v<N>` with lower-case letters for family and size and N ≥ 1
  without a leading zero. Adding a provider is adding one rule here and its name to
  `KnownProvider` (`test_registry_response_value_sets_match_the_domain` holds them equal). Pure.
"""

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

# The known providers as a type, for the registry's published response bodies; kept equal to
# the keys of FULL_MODEL_ID_RULES by test_registry_response_value_sets_match_the_domain.
KnownProvider = Literal["mock"]

FULL_MODEL_ID_RULES: Mapping[str, re.Pattern[str]] = MappingProxyType(
    {"mock": re.compile(r"mock-[a-z]+-[a-z]+-v[1-9][0-9]*")}
)


def is_known_provider(provider: str) -> bool:
    """Whether the provider has a full-model-ID rule."""
    return provider in FULL_MODEL_ID_RULES


def is_full_model_id(provider: str, model: str) -> bool:
    """Whether `model` is a full model ID of the known `provider` (an alias is not)."""
    return FULL_MODEL_ID_RULES[provider].fullmatch(model) is not None
