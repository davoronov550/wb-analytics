"""Catalog outbound ports (what the application needs from the outside).

Concrete adapters (Django repository, httpx WB gateway) implement these; use cases
depend only on the interfaces.
"""

from __future__ import annotations

from typing import Protocol

from catalog.application.dto import (
    Ordering,
    Page,
    ProductFilter,
    RawProduct,
    UpsertResult,
)
from catalog.domain.product import Product

__all__ = ["ProductRepositoryPort", "WbCatalogGatewayPort"]


class ProductRepositoryPort(Protocol):
    def upsert_many(self, products: list[Product], source_query: str) -> UpsertResult:
        """Insert or update products by wb_id (idempotent); link to the query."""
        ...

    def list(
        self,
        filter: ProductFilter,
        ordering: Ordering,
        page: int,
        page_size: int,
    ) -> Page[Product]:
        """Return a filtered, ordered, paginated page of products."""
        ...


class WbCatalogGatewayPort(Protocol):
    def fetch(self, query: str, max_pages: int) -> list[RawProduct]:
        """Fetch raw products for a query from Wildberries (paginated, resilient)."""
        ...
