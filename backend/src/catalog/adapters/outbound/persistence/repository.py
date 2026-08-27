"""Django implementation of ProductRepositoryPort (outbound adapter).

The only place catalog persistence logic lives. Translates the application's
``ProductFilter``/``Ordering`` into ORM queries and maps rows back to domain
Products; the use cases never see a Model.
"""

from __future__ import annotations

from django.db import transaction

from catalog.adapters.outbound.persistence.mappers import to_defaults, to_domain
from catalog.adapters.outbound.persistence.models import ProductModel, SearchQueryModel
from catalog.application.dto import Ordering, Page, ProductFilter, UpsertResult
from catalog.domain.product import Product

# Columns an existing row takes from the incoming batch. `created_at` is absent on
# purpose: a re-seen product keeps its original creation time.
_UPSERT_COLUMNS = (
    "name",
    "price",
    "sale_price",
    "rating",
    "reviews_count",
    "source_query",
    "updated_at",
)


class DjangoProductRepository:
    @transaction.atomic
    def upsert_many(self, products: list[Product], source_query: str) -> UpsertResult:
        """Insert-or-update the whole batch in one statement.

        A collection run brings hundreds of products at once, so this is a single
        `INSERT ... ON CONFLICT (wb_id) DO UPDATE` rather than a query per product.

        `bulk_create` cannot report which rows it inserted versus updated, and that
        split is part of this port's contract (it surfaces in the CLI summary, in
        ParseJob and in GET /api/tasks/{id}/). So the ids already present are read
        first, in one query, and the counts come from set arithmetic.

        Wrapped in a transaction: the products and the query's `collected_count`
        must move together or not at all.
        """
        query_row, _ = SearchQueryModel.objects.get_or_create(text=source_query)

        incoming = {product.wb_id: product for product in products}
        existing_ids = set(
            ProductModel.objects.filter(wb_id__in=incoming).values_list("wb_id", flat=True)
        )

        rows = [
            ProductModel(wb_id=wb_id, source_query=query_row, **to_defaults(product))
            for wb_id, product in incoming.items()
        ]
        if rows:
            ProductModel.objects.bulk_create(
                rows,
                update_conflicts=True,
                unique_fields=["wb_id"],
                update_fields=list(_UPSERT_COLUMNS),
            )

        query_row.collected_count = query_row.products.count()
        query_row.save(update_fields=["collected_count"])
        return UpsertResult(
            created=len(incoming.keys() - existing_ids),
            updated=len(incoming.keys() & existing_ids),
        )

    def list(
        self,
        filter: ProductFilter,
        ordering: Ordering,
        page: int,
        page_size: int,
    ) -> Page[Product]:
        qs = ProductModel.objects.select_related("source_query").all()
        # Price bounds apply to sale price (what the buyer pays).
        if filter.min_price is not None:
            qs = qs.filter(sale_price__gte=filter.min_price)
        if filter.max_price is not None:
            qs = qs.filter(sale_price__lte=filter.max_price)
        if filter.min_rating is not None:
            qs = qs.filter(rating__gte=filter.min_rating)
        if filter.max_rating is not None:
            qs = qs.filter(rating__lte=filter.max_rating)
        if filter.min_reviews is not None:
            qs = qs.filter(reviews_count__gte=filter.min_reviews)
        if filter.max_reviews is not None:
            qs = qs.filter(reviews_count__lte=filter.max_reviews)
        if filter.query:
            qs = qs.filter(source_query__text__iexact=filter.query)

        prefix = "-" if ordering.descending else ""
        # `wb_id` is a stable tie-breaker so pagination is deterministic.
        qs = qs.order_by(f"{prefix}{ordering.field}", "wb_id")

        count = qs.count()
        start = (page - 1) * page_size
        items = [to_domain(row) for row in qs[start : start + page_size]]
        return Page(items=items, count=count, page=page, page_size=page_size)
