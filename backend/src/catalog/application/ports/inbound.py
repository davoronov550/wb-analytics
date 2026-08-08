"""Catalog inbound ports (what the application can do).

Inbound adapters (HTTP views, CLI command, Celery task) depend on these
interfaces; the use-case implementations live in ``application/use_cases`` (T027,
T036).
"""

from __future__ import annotations

from typing import Protocol

from catalog.application.dto import (
    CollectInput,
    CollectResult,
    Ordering,
    Page,
    ProductFilter,
    ProductView,
)

__all__ = ["CollectProducts", "ListProducts"]


class CollectProducts(Protocol):
    def execute(self, command: CollectInput) -> CollectResult:
        """Collect products for a query from WB and upsert them."""
        ...


class ListProducts(Protocol):
    def execute(
        self,
        filter: ProductFilter,
        ordering: Ordering,
        page: int,
        page_size: int,
    ) -> Page[ProductView]:
        """Return a filtered, ordered, paginated page of product views."""
        ...
