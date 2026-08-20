"""ListProducts use case (application) — framework-free.

Reads a filtered/ordered page of domain Products from the repository and maps each
to a ProductView (adding discount fields via the domain policy). Depends only on
the repository port.
"""

from __future__ import annotations

from catalog.application.dto import Ordering, Page, ProductFilter, ProductView
from catalog.application.ports.outbound import ProductRepositoryPort
from catalog.domain.discount import discount_abs, discount_pct
from catalog.domain.product import Product


class ListProducts:
    def __init__(self, *, repository: ProductRepositoryPort) -> None:
        self._repository = repository

    def execute(
        self,
        filter: ProductFilter,
        ordering: Ordering,
        page: int,
        page_size: int,
    ) -> Page[ProductView]:
        result = self._repository.list(filter, ordering, page, page_size)
        return Page(
            items=[self._to_view(product) for product in result.items],
            count=result.count,
            page=result.page,
            page_size=result.page_size,
        )

    @staticmethod
    def _to_view(product: Product) -> ProductView:
        return ProductView(
            wb_id=product.wb_id,
            name=product.name,
            price=product.price.amount,
            sale_price=product.sale_price.amount,
            discount_abs=discount_abs(product).amount,
            discount_pct=discount_pct(product),
            rating=product.rating.value,
            reviews_count=product.reviews_count.value,
            query=product.source_query,
            updated_at=None,
        )
