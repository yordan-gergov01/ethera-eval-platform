"""Frozen records the registry's repositories return instead of ORM objects.

Role: `ProductRecord`, `ManifestRecord`, `ProductSummary` and `ProductPage`.
Used by: `evals.registry.repositories.products`, `.manifests`; `evals.registry.services`;
  `evals.registry.api` (response mapping).
Depends on: `evals.registry.domain` (`Manifest`, `ModelBinding`).
Key invariants: immutable values; usernames appear only as `created_by` / `changed_by`, the
  user who created a version (contract §2), never in logs or audit details.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from evals.registry.domain import Manifest, ModelBinding


@dataclass(frozen=True, slots=True)
class ProductRecord:
    """A Product's identity; `id` is the `entity_id` of its audit rows."""

    id: UUID
    client_id: str
    project_id: str


@dataclass(frozen=True, slots=True)
class ManifestRecord:
    """One Manifest version as stored: the accepted text, its parsed sections and who made it."""

    version: int
    manifest: Manifest
    document: str
    created_at: datetime
    created_by: str


@dataclass(frozen=True, slots=True)
class ProductSummary:
    """A Product with the headline of its current Manifest version."""

    client_id: str
    project_id: str
    manifest_version: int
    generation_binding: ModelBinding
    changed_at: datetime
    changed_by: str


@dataclass(frozen=True, slots=True)
class ProductPage:
    """One page of Products and the size of the whole set."""

    items: tuple[ProductSummary, ...]
    total: int
