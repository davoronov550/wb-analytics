"""Django implementation of ProductRepositoryPort (outbound adapter).

The only place catalog persistence logic lives. Translates the application's
``ProductFilter``/``Ordering`` into ORM queries and maps rows back to domain
Products; the use cases never see a Model.
"""

from __future__ import annotations

from catalog.adapters.outbound.persistence.mappers import to_defaults, to_domain
from catalog.adapters.outbound.persistence.models import ProductModel, SearchQueryModel
from catalog.application.dto import Ordering, Page, ProductFilter, UpsertResult
from catalog.domain.product import Product


class DjangoProductRepository:
    def upsert_many(self, products: list[Product], source_query: str) -> UpsertResult:
        query_row, _ = SearchQueryModel.objects.get_or_create(text=source_query)
        created = 0
        updated = 0
        for product in products:
            _, was_created = ProductModel.objects.update_or_create(
                wb_id=product.wb_id,
                defaults={**to_defaults(product), "source_query": query_row},
            )
            if was_created:
                created += 1
            else:
                updated += 1
        query_row.collected_count = query_row.products.count()
        query_row.save(update_fields=["collected_count"])
        return UpsertResult(created=created, updated=updated)

    def list(
        self,
        filter: ProductFilter,
        ordering: Ordering,
        page: int,
        page_size: int,
    ) -> Page[Product]:
        qs = ProductModel.objects.select_related("source_query").all()
        # Price bounds apply to sale price (what the buyer pays) — FR-007.
        if filter.min_price is not None:
            qs = qs.filter(sale_price__gte=filter.min_price)
        if filter.max_price is not None:
            qs = qs.filter(sale_price__lte=filter.max_price)
        if filter.min_rating is not None:
            qs = qs.filter(rating__gte=filter.min_rating)
        if filter.min_reviews is not None:
            qs = qs.filter(reviews_count__gte=filter.min_reviews)
        if filter.query:
            qs = qs.filter(source_query__text__iexact=filter.query)

        prefix = "-" if ordering.descending else ""
        # `wb_id` is a stable tie-breaker so pagination is deterministic.
        qs = qs.order_by(f"{prefix}{ordering.field}", "wb_id")

        count = qs.count()
        start = (page - 1) * page_size
        items = [to_domain(row) for row in qs[start : start + page_size]]
        return Page(items=items, count=count, page=page, page_size=page_size)
