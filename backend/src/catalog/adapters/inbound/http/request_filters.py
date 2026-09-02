"""Parse & validate list query params into application DTOs (inbound HTTP adapter).

Framework filtering (django-filter/OrderingFilter) would live here too, but the
mapping to the application's ProductFilter/Ordering is explicit so the use case
stays framework-free. Invalid input raises InvalidFilter → 400 via the exception
handler.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from catalog.application.dto import ORDERABLE_FIELDS, Ordering, ProductFilter
from catalog.application.errors import InvalidFilter

# Bounds of the columns these filters compare against. A filter value is never
# stored, which is what made this look exempt — but it still reaches PostgreSQL
# inside the WHERE clause, and a comparison against a value wider than the
# column raises there exactly as an INSERT would. `min_reviews` did, as a 500.
#
# `ProductModel.reviews_count` is a PositiveIntegerField (PostgreSQL integer);
# `price` and `sale_price` are DECIMAL(10, 2).
_REVIEWS_MAX = 2**31 - 1
_PRICE_MAX = Decimal("99999999.99")
#: `wb_id` is a BigIntegerField, and `<int:wb_id>` in the URLconf matches any
#: run of digits — so the path carries the same risk as a body field.
BIGINT_MAX = 2**63 - 1


def _decimal(params: Mapping, key: str) -> Decimal | None:
    raw = params.get(key)
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvalidFilter(f"{key} must be a number") from exc


def _int(params: Mapping, key: str) -> int | None:
    raw = params.get(key)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (ValueError, TypeError) as exc:
        raise InvalidFilter(f"{key} must be an integer") from exc


def parse_product_filter(params: Mapping) -> ProductFilter:
    min_price = _decimal(params, "min_price")
    max_price = _decimal(params, "max_price")
    min_rating = _decimal(params, "min_rating")
    max_rating = _decimal(params, "max_rating")
    min_reviews = _int(params, "min_reviews")
    max_reviews = _int(params, "max_reviews")
    query = params.get("query") or None

    for key, amount in (("min_price", min_price), ("max_price", max_price)):
        if amount is None:
            continue
        if not amount.is_finite():
            raise InvalidFilter(f"{key} must be a finite number")
        if amount < 0:
            raise InvalidFilter(f"{key} must be >= 0")
        if amount > _PRICE_MAX:
            raise InvalidFilter(f"{key} must be <= {_PRICE_MAX}")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise InvalidFilter("min_price must be <= max_price")
    for key, value in (("min_rating", min_rating), ("max_rating", max_rating)):
        if value is not None and not (Decimal("0") <= value <= Decimal("5")):
            raise InvalidFilter(f"{key} must be within [0, 5]")
    if min_rating is not None and max_rating is not None and min_rating > max_rating:
        raise InvalidFilter("min_rating must be <= max_rating")
    for key, count in (("min_reviews", min_reviews), ("max_reviews", max_reviews)):
        if count is None:
            continue
        if count < 0:
            raise InvalidFilter(f"{key} must be >= 0")
        if count > _REVIEWS_MAX:
            raise InvalidFilter(f"{key} must be <= {_REVIEWS_MAX}")
    if min_reviews is not None and max_reviews is not None and min_reviews > max_reviews:
        raise InvalidFilter("min_reviews must be <= max_reviews")

    return ProductFilter(
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        max_rating=max_rating,
        min_reviews=min_reviews,
        max_reviews=max_reviews,
        query=query,
    )


def parse_ordering(params: Mapping) -> Ordering:
    raw = params.get("ordering")
    if not raw:
        return Ordering()  # default: reviews_count desc
    descending = raw.startswith("-")
    field = raw[1:] if descending else raw
    if field not in ORDERABLE_FIELDS:
        raise InvalidFilter(f"Cannot order by {field!r}; allowed: {sorted(ORDERABLE_FIELDS)}")
    return Ordering(field=field, descending=descending)
