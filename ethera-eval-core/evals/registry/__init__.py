"""The Product registry: Products, their versioned Manifests and Model Bindings.

Role: the module's barrel — its mount for `evals.MODULES` and the services other code may use
  (creating a Product the way the seed does, the demo Manifest text).
Used by: `evals.MODULES`; tests/integration/registry_fixtures.py.
Depends on: `evals.registry.module`, `evals.registry.services`.
Key invariants: outsiders import this barrel only, never the module's layers.
"""

from evals.registry.module import REGISTRY
from evals.registry.services import create_product, demo_document

__all__ = ["REGISTRY", "create_product", "demo_document"]
