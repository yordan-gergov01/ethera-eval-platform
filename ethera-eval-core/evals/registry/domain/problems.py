"""The problems a refused Manifest is reported with.

Role: `ProblemType` (the fixed set of problem kinds of contract §3.3, C-10), `ManifestProblem`
  (one problem: a field path and a kind) and `DOCUMENT_FIELD`, the field of document-level
  problems.
Used by: `evals.registry.domain.yaml_document`, `evals.registry.domain.manifest`, the domain
  barrel; through it `evals.registry.services.manifests`.
Depends on: the standard library only.
Key invariants: the set of kinds is closed and its values are part of the API (`errors[].type`).
  A problem's message is a fixed text per kind: it never quotes a submitted value, so a
  refusal can never echo document content (contract §3.3 "Problems"). Pure: no I/O.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

DOCUMENT_FIELD = "document"


class ProblemType(StrEnum):
    """Every kind of Manifest problem. Values are part of the API: never rename one."""

    MALFORMED = "malformed"
    UNSUPPORTED_SYNTAX = "unsupported_syntax"
    DUPLICATE_KEY = "duplicate_key"
    UNKNOWN_KEY = "unknown_key"
    MISSING = "missing"
    WRONG_TYPE = "wrong_type"
    INVALID_VALUE = "invalid_value"
    PRODUCT_MISMATCH = "product_mismatch"
    UNKNOWN_PROVIDER = "unknown_provider"
    ALIAS = "alias"
    PROVIDER_NOT_ALLOWED = "provider_not_allowed"
    DUPLICATE_ROLE = "duplicate_role"
    GENERATION_REQUIRED = "generation_required"
    DUPLICATE_VALUE = "duplicate_value"


MESSAGES: Mapping[ProblemType, str] = MappingProxyType(
    {
        ProblemType.MALFORMED: (
            "The document is not a single YAML mapping nested at most 10 levels deep."
        ),
        ProblemType.UNSUPPORTED_SYNTAX: (
            "The document uses an anchor, alias, merge key, explicit tag or non-string key."
        ),
        ProblemType.DUPLICATE_KEY: "This key appears more than once in its mapping.",
        ProblemType.UNKNOWN_KEY: "This key is not part of the Manifest.",
        ProblemType.MISSING: "This key is required.",
        ProblemType.WRONG_TYPE: "This value has the wrong type.",
        ProblemType.INVALID_VALUE: "This value is not allowed here.",
        ProblemType.PRODUCT_MISMATCH: "This identifier does not name the Product being changed.",
        ProblemType.UNKNOWN_PROVIDER: "This provider is not known.",
        ProblemType.ALIAS: "This is not a full model ID for its provider.",
        ProblemType.PROVIDER_NOT_ALLOWED: "This provider is not listed in allowed_providers.",
        ProblemType.DUPLICATE_ROLE: "Another binding already has this role.",
        ProblemType.GENERATION_REQUIRED: "Exactly one binding must have the role generation.",
        ProblemType.DUPLICATE_VALUE: "This provider is already listed.",
    }
)


@dataclass(frozen=True, slots=True)
class ManifestProblem:
    """One problem of a refused Manifest: where (`field`, a path) and what kind (`type`)."""

    field: str
    type: ProblemType

    @property
    def message(self) -> str:
        """A fixed text for the kind; never the submitted value."""
        return MESSAGES[self.type]


def document_problem(problem_type: ProblemType) -> ManifestProblem:
    """A problem of the document as a whole."""
    return ManifestProblem(DOCUMENT_FIELD, problem_type)
