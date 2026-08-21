"""Catalog outbound ports (what the application needs from the outside).

Concrete adapters (Django repository, httpx WB gateway) implement these; use cases
depend only on the interfaces.
"""

from __future__ import annotations

from typing import Protocol

from catalog.application.dto import (
    Ordering,
    Page,
    ParseJob,
    ProductFilter,
    RawProduct,
    UpsertResult,
)
from catalog.domain.product import Product

__all__ = ["ProductRepositoryPort", "WbCatalogGatewayPort", "ParseJobRepositoryPort"]


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


class ParseJobRepositoryPort(Protocol):
    def find_active(self, query: str) -> ParseJob | None:
        """Return a pending/running job for the query, if one exists (idempotency)."""
        ...

    def create_pending(self, query: str) -> ParseJob:
        """Create a new pending job (with a fresh task_id) and return it."""
        ...

    def get(self, task_id: str) -> ParseJob | None:
        """Return the job by task_id, or None."""
        ...

    def mark_running(self, task_id: str) -> None: ...

    def mark_done(self, task_id: str, created: int, updated: int) -> None: ...

    def mark_failed(self, task_id: str, error: str) -> None: ...
