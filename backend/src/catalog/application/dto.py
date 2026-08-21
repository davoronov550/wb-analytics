"""Catalog application DTOs — plain data crossing the use-case boundary.

Inbound adapters map transport input to these; use cases return these; the read
model (`ProductView`) is what the HTTP adapter serializes to JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

__all__ = [
    "RawProduct",
    "CollectInput",
    "UpsertResult",
    "CollectResult",
    "ProductView",
    "ProductFilter",
    "Ordering",
    "ORDERABLE_FIELDS",
    "Page",
    "ParseJob",
    "ParseStatus",
    "ACTIVE_PARSE_STATUSES",
]

# Fields the API may sort by (FR-008).
ORDERABLE_FIELDS = frozenset({"price", "sale_price", "rating", "reviews_count", "name"})


class ParseStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# A query with an active job must not be enqueued again (idempotency, FR-022).
ACTIVE_PARSE_STATUSES = frozenset({ParseStatus.PENDING, ParseStatus.RUNNING})


@dataclass(frozen=True)
class ParseJob:
    """Status of an asynchronous collection run (FE-02)."""

    task_id: str
    query: str
    status: str
    created: int = 0
    updated: int = 0
    collected_count: int = 0
    error: str | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class RawProduct:
    """One product as parsed from the WB payload (field fallbacks applied),
    still primitive — the use case maps it to a domain Product."""

    wb_id: int | None
    name: str | None
    price_kopecks: int | None
    sale_price_kopecks: int | None
    rating: object = None
    reviews: object = None


@dataclass(frozen=True)
class CollectInput:
    query: str
    max_pages: int | None = None


@dataclass(frozen=True)
class UpsertResult:
    created: int
    updated: int

    @property
    def collected_count(self) -> int:
        return self.created + self.updated


@dataclass(frozen=True)
class CollectResult:
    query: str
    collected_count: int
    created: int
    updated: int
    finished_at: datetime | None = None


@dataclass(frozen=True)
class ProductView:
    wb_id: int
    name: str
    price: Decimal
    sale_price: Decimal
    discount_abs: Decimal
    discount_pct: Decimal
    rating: Decimal
    reviews_count: int
    query: str | None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ProductFilter:
    """Price bounds apply to sale price (what the buyer pays). All optional."""

    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_rating: Decimal | None = None
    min_reviews: int | None = None
    query: str | None = None


@dataclass(frozen=True)
class Ordering:
    field: str = "reviews_count"
    descending: bool = True

    def __post_init__(self) -> None:
        if self.field not in ORDERABLE_FIELDS:
            raise ValueError(f"Cannot order by {self.field!r}; allowed: {sorted(ORDERABLE_FIELDS)}")


@dataclass(frozen=True)
class Page[T]:
    items: list[T] = field(default_factory=list)
    count: int = 0
    page: int = 1
    page_size: int = 1000
