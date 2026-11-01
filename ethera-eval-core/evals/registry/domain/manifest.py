"""The Manifest: its slice-001 schema, its validation and its comparison.

Role: `ModelBinding` and `Manifest` (the parsed `product`, `bindings` and `allowed_providers`
  sections), `check_manifest(document, client_id, project_id)` — a valid Manifest for that
  Product or every problem of the document (contract §3.3) — and `changed_sections`.
Used by: the domain barrel; through it `evals.registry.services` and
  `evals.registry.repositories` (stored versions are rebuilt as `Manifest` values).
Depends on: `evals.registry.domain.yaml_document`, `.problems`, `.identifiers`, `.providers`.
Key invariants: a pure function of the document and the target Product — no clock, randomness
  or I/O — so the same inputs give the same problems in the same order (§3.4). A
  document-level problem is reported alone (C-11). One cause gives one report: a value that is
  missing or of the wrong type is not checked further; `alias` needs a known provider and a
  model of 1 to 128 characters; `duplicate_role` / `generation_required` need every binding to be
  a mapping with a valid role; `provider_not_allowed` needs `allowed_providers` to be a non-empty
  list of strings; `product_mismatch` needs a well-formed identifier; `unknown_provider` and
  `duplicate_value` are independent, so a repeated unknown provider gets both
  (`test_duplicate_unknown_provider_reports_both_problems`). Each (field, type) pair is
  reported at most once. Two Manifests are equal iff their parsed sections are (C-4): text,
  comments, quoting and key order do not count, binding order does.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from evals.registry.domain.identifiers import is_identifier
from evals.registry.domain.problems import ManifestProblem, ProblemType
from evals.registry.domain.providers import is_full_model_id, is_known_provider
from evals.registry.domain.yaml_document import YamlMapping, YamlValue, join, read_document

SECTIONS = ("product", "bindings", "allowed_providers")
PRODUCT_KEYS = ("client_id", "project_id")
BINDING_KEYS = ("role", "provider", "model")
MODEL_MAX_LENGTH = 128


class BindingRole(StrEnum):
    """The roles a Model Binding can have (glossary value set)."""

    GENERATION = "generation"
    JUDGE = "judge"
    EMBEDDING = "embedding"


ROLES = frozenset(role.value for role in BindingRole)


@dataclass(frozen=True, slots=True)
class ModelBinding:
    """A role bound to a provider and a full model ID."""

    role: str
    provider: str
    model: str


@dataclass(frozen=True, slots=True)
class Manifest:
    """The parsed sections of one Manifest version; equality is C-4's equality."""

    client_id: str
    project_id: str
    bindings: tuple[ModelBinding, ...]
    allowed_providers: tuple[str, ...]

    @property
    def generation_binding(self) -> ModelBinding:
        """The one `generation` binding (INV-REG-05)."""
        return next(b for b in self.bindings if b.role == BindingRole.GENERATION)


def changed_sections(before: Manifest, after: Manifest) -> tuple[str, ...]:
    """The sorted top-level section names whose parsed value differs."""
    changed = []
    if (before.client_id, before.project_id) != (after.client_id, after.project_id):
        changed.append("product")
    if before.bindings != after.bindings:
        changed.append("bindings")
    if before.allowed_providers != after.allowed_providers:
        changed.append("allowed_providers")
    return tuple(sorted(changed))


def check_manifest(
    document: str, client_id: str, project_id: str
) -> Manifest | tuple[ManifestProblem, ...]:
    """The Manifest of `document` for Product (`client_id`, `project_id`), or its problems."""
    tree = read_document(document)
    if isinstance(tree, ManifestProblem):
        return (tree,)
    checker = _Checker(client_id, project_id)
    bindings, allowed = checker.check(tree)
    if checker.problems or bindings is None or allowed is None:
        return tuple(checker.problems)
    return Manifest(client_id, project_id, tuple(bindings), tuple(allowed))


_ABSENT = object()


@dataclass
class _Checker:
    client_id: str
    project_id: str
    problems: list[ManifestProblem] = field(default_factory=list)

    def report(self, path: str, problem_type: ProblemType) -> None:
        problem = ManifestProblem(path, problem_type)
        if problem not in self.problems:
            self.problems.append(problem)

    def check(self, tree: YamlMapping) -> tuple[list[ModelBinding] | None, list[str] | None]:
        self.unknown_keys(tree, "", SECTIONS)
        self.product(tree.get("product", _ABSENT))
        bindings = self.bindings(tree.get("bindings", _ABSENT))
        allowed = self.allowed_providers(tree.get("allowed_providers", _ABSENT))
        if bindings is not None and allowed is not None:
            for index, binding in enumerate(bindings):
                provider = binding.get("provider")
                if isinstance(provider, str) and provider not in allowed:
                    self.report(f"bindings[{index}].provider", ProblemType.PROVIDER_NOT_ALLOWED)
        if bindings is None or allowed is None:
            return None, None
        return [_binding(b) for b in bindings if _is_complete(b)], allowed

    def unknown_keys(self, mapping: YamlMapping, path: str, known: Sequence[str]) -> None:
        for key in mapping:
            if key not in known:
                self.report(join(path, key), ProblemType.UNKNOWN_KEY)

    def present(self, value: object, path: str, expected: type) -> bool:
        """Report `missing` or `wrong_type`; True when the value can be checked further."""
        if value is _ABSENT:
            self.report(path, ProblemType.MISSING)
            return False
        if not isinstance(value, expected):
            self.report(path, ProblemType.WRONG_TYPE)
            return False
        return True

    def string(self, mapping: YamlMapping, key: str, path: str) -> str | None:
        value = mapping.get(key, _ABSENT)
        return value if self.present(value, join(path, key), str) else None  # type: ignore[return-value]

    def product(self, value: object) -> None:
        if not self.present(value, "product", dict):
            return
        section: YamlMapping = value  # type: ignore[assignment]
        self.unknown_keys(section, "product", PRODUCT_KEYS)
        for key, target in (("client_id", self.client_id), ("project_id", self.project_id)):
            identifier = self.string(section, key, "product")
            if identifier is None:
                continue
            if not is_identifier(identifier):
                self.report(f"product.{key}", ProblemType.INVALID_VALUE)
            elif identifier != target:
                self.report(f"product.{key}", ProblemType.PRODUCT_MISMATCH)

    def bindings(self, value: object) -> list[YamlMapping] | None:
        """The bindings that are mappings; None when the section cannot be checked further."""
        if not self.present(value, "bindings", list):
            return None
        items: list[YamlValue] = value  # type: ignore[assignment]
        mappings: list[YamlMapping] = []
        roles: list[str] | None = []
        for index, item in enumerate(items):
            path = f"bindings[{index}]"
            if not self.present(item, path, dict):
                roles = None
                mappings.append({})
                continue
            binding: YamlMapping = item  # type: ignore[assignment]
            mappings.append(binding)
            role = self.binding(binding, path)
            if role is None or roles is None:
                roles = None
            else:
                roles.append(role)
        if roles is not None:
            self.roles(roles)
        return mappings

    def binding(self, binding: YamlMapping, path: str) -> str | None:
        """Check one binding; return its role when it is valid."""
        self.unknown_keys(binding, path, BINDING_KEYS)
        role = self.string(binding, "role", path)
        if role is not None and role not in ROLES:
            self.report(f"{path}.role", ProblemType.INVALID_VALUE)
            role = None
        provider = self.string(binding, "provider", path)
        known = provider is not None and is_known_provider(provider)
        if provider is not None and not known:
            self.report(f"{path}.provider", ProblemType.UNKNOWN_PROVIDER)
        model = self.string(binding, "model", path)
        if model is not None:
            if not 1 <= len(model) <= MODEL_MAX_LENGTH:
                self.report(f"{path}.model", ProblemType.INVALID_VALUE)
            elif known and provider is not None and not is_full_model_id(provider, model):
                self.report(f"{path}.model", ProblemType.ALIAS)
        return role

    def roles(self, roles: list[str]) -> None:
        seen: set[str] = set()
        for index, role in enumerate(roles):
            if role in seen:
                self.report(f"bindings[{index}].role", ProblemType.DUPLICATE_ROLE)
            seen.add(role)
        if BindingRole.GENERATION not in seen:
            self.report("bindings", ProblemType.GENERATION_REQUIRED)

    def allowed_providers(self, value: object) -> list[str] | None:
        """The list when it is a non-empty list of strings; None otherwise."""
        if not self.present(value, "allowed_providers", list):
            return None
        items: list[YamlValue] = value  # type: ignore[assignment]
        if not items:
            self.report("allowed_providers", ProblemType.INVALID_VALUE)
            return None
        providers: list[str] | None = []
        seen: set[str] = set()
        for index, item in enumerate(items):
            path = f"allowed_providers[{index}]"
            if not self.present(item, path, str):
                providers = None
                continue
            provider: str = item  # type: ignore[assignment]
            # Independent checks: a repeated unknown provider is reported as both.
            if not is_known_provider(provider):
                self.report(path, ProblemType.UNKNOWN_PROVIDER)
            if provider in seen:
                self.report(path, ProblemType.DUPLICATE_VALUE)
            seen.add(provider)
            if providers is not None:
                providers.append(provider)
        return providers


def _is_complete(binding: YamlMapping) -> bool:
    return all(isinstance(binding.get(key), str) for key in BINDING_KEYS)


def _binding(binding: YamlMapping) -> ModelBinding:
    return ModelBinding(str(binding["role"]), str(binding["provider"]), str(binding["model"]))
