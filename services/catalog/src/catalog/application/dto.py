"""Catalog application DTOs — plain data crossing the use-case boundary.

Inbound adapters map transport input to these; use cases return these; the read
model (`ProductView`) is what the HTTP adapter serializes to JSON.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final

__all__ = [
    "ACTIVE_PARSE_STATUSES",
    "ORDERABLE_FIELDS",
    "CollectInput",
    "CollectResult",
    "Ordering",
    "SortKey",
    "Page",
    "ParseJob",
    "ParseStatus",
    "ProductFilter",
    "ProductView",
    "RawProduct",
    "UpsertResult",
]

# Fields the API may sort by.
ORDERABLE_FIELDS = frozenset({"price", "sale_price", "rating", "reviews_count", "name"})


class ParseStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# A query with an active job must not be enqueued again (idempotency).
ACTIVE_PARSE_STATUSES = frozenset({ParseStatus.PENDING, ParseStatus.RUNNING})


@dataclass(frozen=True)
class ParseJob:
    """Status of an asynchronous collection run."""

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
    """Price/rating/reviews are two-sided ranges; price bounds apply to sale
    price (what the buyer pays). All optional and combined with AND."""

    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_rating: Decimal | None = None
    max_rating: Decimal | None = None
    min_reviews: int | None = None
    max_reviews: int | None = None
    query: str | None = None


@dataclass(frozen=True)
class SortKey:
    """One level of the sort: a field and its direction.

    Ascending by default, as in SQL — the interesting direction is then stated
    at the call site instead of inherited from a default nobody re-reads.
    """

    field: str
    descending: bool = False


#: What `Ordering()` means when nothing is asked for. Kept as a module-level
#: constant rather than inlined: `__post_init__` tells "keys were given" from
#: "keys were defaulted" by identity with this object.
_DEFAULT_KEYS: Final[tuple[SortKey, ...]] = (SortKey("reviews_count", descending=True),)


@dataclass(frozen=True)
class Ordering:
    """The sort, as a list of levels.

    It used to be one field. `SortBuilder.tsx` has always built any number of
    levels, and `buildProductsQuery` shipped only the first — the rest was
    applied in the browser over the same thousand-row page. That works only
    while the page holds everything; with server-side pagination a page ordered
    by the first level and re-sorted by the client holds the *wrong rows*, not
    merely rows in the wrong order.

    This is the one sanctioned edit to the copied application layer
    (док. 7, §7.6). `Ordering(field=...)` therefore keeps working and means a
    list of one, so nothing that already calls it has to change.
    """

    keys: tuple[SortKey, ...] = _DEFAULT_KEYS
    #: The pre-T110 spelling. `InitVar`, not a field: it is a way to build
    #: `keys`, and keeping it as an attribute as well would invite code to read
    #: the first level and ignore the rest — the bug this change removes.
    field: InitVar[str | None] = None
    descending: InitVar[bool | None] = None

    def __post_init__(self, field: str | None, descending: bool | None) -> None:
        if field is not None:
            if self.keys is not _DEFAULT_KEYS:
                raise ValueError("Ordering takes `keys` or `field`, not both.")
            # The old default was descending; `None` here means "not stated".
            object.__setattr__(self, "keys", (SortKey(field, descending is not False),))
        elif descending is not None:
            raise ValueError("Ordering takes `descending` only together with `field`.")

        if not self.keys:
            # An ordering with no levels has no defined row order, and keyset
            # pagination over an undefined order repeats and skips rows.
            raise ValueError("Ordering needs at least one key.")

        unknown = sorted({key.field for key in self.keys} - ORDERABLE_FIELDS)
        if unknown:
            listed = ", ".join(repr(name) for name in unknown)
            raise ValueError(f"Cannot order by {listed}; allowed: {sorted(ORDERABLE_FIELDS)}")


@dataclass(frozen=True)
class Page[T]:
    items: list[T] = field(default_factory=list)
    count: int = 0
    page: int = 1
    page_size: int = 1000
