"""Use cases of the registry: reading Products, changing Manifests, seeding the demo Product.

Role: re-exports the registry's services.
Used by: `evals.registry.api`, `evals.registry.module`, the `evals.registry` barrel.
Depends on: `evals.registry.services.products`, `.manifests`, `.seed`, `.access`, `.lookup`.
Key invariants: none.
"""

from evals.registry.services.access import member_client_ids_for
from evals.registry.services.lookup import get_visible_product
from evals.registry.services.manifests import ManifestReplacement, create_product, replace_manifest
from evals.registry.services.products import ProductDetails, get_product, list_products
from evals.registry.services.seed import demo_document, seed_demo_product

__all__ = [
    "ManifestReplacement",
    "ProductDetails",
    "create_product",
    "demo_document",
    "get_product",
    "get_visible_product",
    "list_products",
    "member_client_ids_for",
    "replace_manifest",
    "seed_demo_product",
]
