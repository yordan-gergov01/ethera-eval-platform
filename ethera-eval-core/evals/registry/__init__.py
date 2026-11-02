"""The Product registry: Products, their versioned Manifests and Model Bindings.

Role: the module's barrel — its mount for `evals.MODULES` and the services other code may use
  (creating a Product the way the seed does, the demo Manifest text). Appended in slice 002
  (R-201): the membership gate, the connection-taking Product lookup and `ProductRecord`, so
  `evaluation` reaches a Product inside its own single tenant transaction.
Used by: `evals.MODULES`; `evals.evaluation.services`; tests/integration/registry_fixtures.py.
Depends on: `evals.registry.module`, `evals.registry.services`, `evals.registry.repositories`.
Key invariants: outsiders import this barrel only, never the module's layers.
"""

from evals.registry.module import REGISTRY
from evals.registry.repositories import ProductRecord
from evals.registry.services import (
    create_product,
    demo_document,
    get_visible_product,
    member_client_ids_for,
)

__all__ = [
    "REGISTRY",
    "ProductRecord",
    "create_product",
    "demo_document",
    "get_visible_product",
    "member_client_ids_for",
]
