"""DB-side statistics over catalog products (implements StatsQueryPort, FE-05).

Aggregation runs in PostgreSQL (avg/stddev/count/discount share via ORM; median via
PERCENTILE_CONT), so it stays fast on large sets (SC-010). Reuses catalog's
ProductFilter semantics (price bounds apply to sale_price).
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import (
    Aggregate,
    Avg,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    StdDev,
)

from analytics.application.dto import Stats, TopProduct
from catalog.adapters.outbound.persistence.models import ProductModel
from catalog.application.dto import ProductFilter

_MONEY = DecimalField(max_digits=10, decimal_places=2)
_QUANT = Decimal("0.01")


class Median(Aggregate):
    function = "PERCENTILE_CONT"
    name = "median"
    template = "%(function)s(0.5) WITHIN GROUP (ORDER BY %(expressions)s)"
    output_field = _MONEY


def _apply_filter(qs, filter: ProductFilter):
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
    return qs


def _money(value) -> Decimal:
    return (value if value is not None else Decimal("0")).quantize(_QUANT)


class DjangoStatsQuery:
    def aggregate(self, filter: ProductFilter) -> Stats:
        qs = _apply_filter(ProductModel.objects.all(), filter)
        discount_expr = ExpressionWrapper(F("price") - F("sale_price"), output_field=_MONEY)
        agg = qs.aggregate(
            count=Count("id"),
            avg_price=Avg("sale_price"),
            median_price=Median("sale_price"),
            price_stddev=StdDev("sale_price"),
            avg_discount=Avg(discount_expr),
            on_sale=Count("id", filter=Q(sale_price__lt=F("price"))),
        )
        count = agg["count"] or 0
        top = [
            TopProduct(wb_id=row["wb_id"], name=row["name"], reviews_count=row["reviews_count"])
            for row in qs.order_by("-reviews_count").values("wb_id", "name", "reviews_count")[:5]
        ]
        return Stats(
            count=count,
            avg_price=_money(agg["avg_price"]),
            median_price=_money(agg["median_price"]),
            price_stddev=_money(agg["price_stddev"]),
            avg_discount_abs=_money(agg["avg_discount"]),
            discount_share=round((agg["on_sale"] / count) if count else 0.0, 4),
            top_by_reviews=top,
        )
