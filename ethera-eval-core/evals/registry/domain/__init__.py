"""The registry's domain: Manifests, Model Bindings, identifiers and Manifest problems.

Role: re-exports the pure domain the registry's repositories and services use.
Used by: `evals.registry.repositories`, `evals.registry.services`, `evals.registry.api.schemas`
  (`BindingRole`, `KnownProvider`); tests/unit/evals/registry/.
Depends on: `evals.registry.domain.manifest`, `.problems`, `.identifiers`, `.providers`.
Key invariants: pure — no framework, ORM, broker, HTTP or logging import, no I/O, no clock
  (import-linter contract "The registry domain is pure").
"""

from evals.registry.domain.identifiers import is_identifier
from evals.registry.domain.manifest import (
    BindingRole,
    Manifest,
    ModelBinding,
    changed_sections,
    check_manifest,
)
from evals.registry.domain.problems import ManifestProblem, ProblemType
from evals.registry.domain.providers import KnownProvider

__all__ = [
    "BindingRole",
    "KnownProvider",
    "Manifest",
    "ManifestProblem",
    "ModelBinding",
    "ProblemType",
    "changed_sections",
    "check_manifest",
    "is_identifier",
]
