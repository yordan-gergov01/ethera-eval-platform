"""Data access of the registry: Products and Manifest versions.

Role: re-exports the repositories and the records they return.
Used by: `evals.registry.services`; tests/integration/evals/registry/.
Depends on: `evals.registry.repositories.products`, `.manifests`, `.records`.
Key invariants: none.
"""

from evals.registry.repositories.manifests import ManifestRepository
from evals.registry.repositories.products import ProductRepository
from evals.registry.repositories.records import (
    ManifestRecord,
    ProductPage,
    ProductRecord,
    ProductSummary,
)

__all__ = [
    "ManifestRecord",
    "ManifestRepository",
    "ProductPage",
    "ProductRecord",
    "ProductRepository",
    "ProductSummary",
]
