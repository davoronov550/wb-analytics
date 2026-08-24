"""Analytics application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SnapshotInput:
    """Current product figures to snapshot (read from the catalog on collection)."""

    wb_id: int
    price: Decimal
    sale_price: Decimal
    rating: Decimal


@dataclass(frozen=True)
class TopProduct:
    wb_id: int
    name: str
    reviews_count: int


@dataclass(frozen=True)
class Stats:
    """Aggregates over a filtered product set."""

    count: int
    avg_price: Decimal
    median_price: Decimal
    price_stddev: Decimal
    avg_discount_abs: Decimal
    discount_share: float
    top_by_reviews: list[TopProduct]


@dataclass(frozen=True)
class QueryStats:
    """Stats for one query, used in side-by-side comparison."""

    query: str
    stats: Stats
