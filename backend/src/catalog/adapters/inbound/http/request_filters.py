"""Parse & validate list query params into application DTOs (inbound HTTP adapter).

Framework filtering (django-filter/OrderingFilter) would live here too, but the
mapping to the application's ProductFilter/Ordering is explicit so the use case
stays framework-free. Invalid input raises InvalidFilter → 400 via the exception
handler (FR-009, SC-005).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from catalog.application.dto import ORDERABLE_FIELDS, Ordering, ProductFilter
from catalog.application.errors import InvalidFilter


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
    min_reviews = _int(params, "min_reviews")
    query = params.get("query") or None

    if min_price is not None and min_price < 0:
        raise InvalidFilter("min_price must be >= 0")
    if max_price is not None and max_price < 0:
        raise InvalidFilter("max_price must be >= 0")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise InvalidFilter("min_price must be <= max_price")
    if min_rating is not None and not (Decimal("0") <= min_rating <= Decimal("5")):
        raise InvalidFilter("min_rating must be within [0, 5]")
    if min_reviews is not None and min_reviews < 0:
        raise InvalidFilter("min_reviews must be >= 0")

    return ProductFilter(
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        min_reviews=min_reviews,
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
