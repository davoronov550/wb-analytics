"""ExportProducts use case (FE-08) — the filtered product set as export rows.

Reuses catalog's ListProducts so an export matches exactly what the table shows.
The row shape is format-agnostic; CSV/XLSX serialization is an adapter concern.
"""

from __future__ import annotations

from catalog.application.dto import Ordering, ProductFilter
from catalog.application.ports.inbound import ListProducts

_EXPORT_PAGE_SIZE = 100_000


class ExportProducts:
    def __init__(self, *, list_products: ListProducts) -> None:
        self._list_products = list_products

    def execute(
        self, filter: ProductFilter, ordering: Ordering, page_size: int = _EXPORT_PAGE_SIZE
    ) -> list[dict]:
        page = self._list_products.execute(filter, ordering, 1, page_size)
        return [self._row(view) for view in page.items]

    @staticmethod
    def _row(view) -> dict:
        return {
            "wb_id": view.wb_id,
            "name": view.name,
            "price": str(view.price),
            "sale_price": str(view.sale_price),
            "discount_abs": str(view.discount_abs),
            "discount_pct": str(view.discount_pct),
            "rating": str(view.rating),
            "reviews_count": view.reviews_count,
            "query": view.query,
        }
