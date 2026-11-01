"""Request and response bodies of the registry's HTTP surface (contract §2).

Role: `ManifestReplace` (the PUT body), `ManifestResponse`, `ProductResponse`,
  `ProductSummaryResponse` and `ProductPageResponse`, with their mapping from service records.
Used by: `evals.registry.api.router`.
Depends on: pydantic; `evals.registry.domain` (`BindingRole`, `KnownProvider`, `ModelBinding`);
  `evals.registry.repositories` records; `evals.registry.services`
  (`ProductDetails`).
Key invariants: the request rejects unknown fields (`extra="forbid"`) and bounds `document` to
  1 to 32,768 characters (C-3); `bindings` and `allowed_providers` keep document order; `document`
  is returned exactly as accepted; timestamps carry a UTC offset. A binding's `role` and
  `provider` and every `allowed_providers` entry are published as enums of the domain's value
  sets (`BindingRole`, `KnownProvider`), so the web's label maps key on generated unions
  (`test_registry_response_value_sets_match_the_domain`).
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from evals.registry.domain import BindingRole, KnownProvider, ModelBinding
from evals.registry.repositories import ManifestRecord, ProductPage, ProductSummary
from evals.registry.services import ProductDetails

MAX_DOCUMENT_LENGTH = 32_768


class ManifestReplace(BaseModel):
    """A replacement: the version being replaced and the new eval.yaml text."""

    model_config = ConfigDict(extra="forbid")

    base_version: Annotated[int, Field(ge=1, strict=True)]
    document: Annotated[str, Field(min_length=1, max_length=MAX_DOCUMENT_LENGTH)]


class ModelBindingResponse(BaseModel):
    role: BindingRole
    provider: KnownProvider
    model: str

    @classmethod
    def of(cls, binding: ModelBinding) -> "ModelBindingResponse":
        # Validated, not cast: a stored Manifest passed the same domain rules on its way in.
        return cls.model_validate(
            {"role": binding.role, "provider": binding.provider, "model": binding.model}
        )


class ManifestResponse(BaseModel):
    version: int
    bindings: list[ModelBindingResponse]
    allowed_providers: list[KnownProvider]
    document: str
    created_at: datetime
    created_by: str

    @classmethod
    def of(cls, record: ManifestRecord) -> "ManifestResponse":
        return cls.model_validate(
            {
                "version": record.version,
                "bindings": [ModelBindingResponse.of(b) for b in record.manifest.bindings],
                "allowed_providers": list(record.manifest.allowed_providers),
                "document": record.document,
                "created_at": record.created_at,
                "created_by": record.created_by,
            }
        )


class ProductResponse(BaseModel):
    client_id: str
    project_id: str
    manifest: ManifestResponse

    @classmethod
    def of(cls, details: ProductDetails) -> "ProductResponse":
        return cls(
            client_id=details.product.client_id,
            project_id=details.product.project_id,
            manifest=ManifestResponse.of(details.manifest),
        )


class ProductSummaryResponse(BaseModel):
    client_id: str
    project_id: str
    manifest_version: int
    generation_binding: ModelBindingResponse
    changed_at: datetime
    changed_by: str

    @classmethod
    def of(cls, summary: ProductSummary) -> "ProductSummaryResponse":
        return cls(
            client_id=summary.client_id,
            project_id=summary.project_id,
            manifest_version=summary.manifest_version,
            generation_binding=ModelBindingResponse.of(summary.generation_binding),
            changed_at=summary.changed_at,
            changed_by=summary.changed_by,
        )


class ProductPageResponse(BaseModel):
    items: list[ProductSummaryResponse]
    total: int
    limit: int
    offset: int

    @classmethod
    def of(cls, page: ProductPage, *, limit: int, offset: int) -> "ProductPageResponse":
        return cls(
            items=[ProductSummaryResponse.of(item) for item in page.items],
            total=page.total,
            limit=limit,
            offset=offset,
        )
