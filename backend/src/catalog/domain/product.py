"""Catalog domain: the Product entity (pure — no framework, no ORM).

Immutable; ``create`` enforces invariants for freshly collected data, while
``rehydrate`` trusts already-validated stored data (used by the persistence
mapper).
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.domain.value_objects import Money, Rating, ReviewsCount


@dataclass(frozen=True)
class Product:
    wb_id: int
    name: str
    price: Money
    sale_price: Money
    rating: Rating
    reviews_count: ReviewsCount
    source_query: str | None = None

    @classmethod
    def create(
        cls,
        *,
        wb_id: int,
        name: str,
        price: Money,
        sale_price: Money,
        rating: Rating,
        reviews_count: ReviewsCount,
        source_query: str | None = None,
    ) -> Product:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Product name must not be empty")
        if wb_id is None or wb_id <= 0:
            raise ValueError(f"Product wb_id must be positive: {wb_id!r}")
        # A sale price above the base price is a bad WB payload — clamp it.
        if sale_price > price:
            sale_price = price
        return cls(
            wb_id=wb_id,
            name=clean_name,
            price=price,
            sale_price=sale_price,
            rating=rating,
            reviews_count=reviews_count,
            source_query=source_query,
        )

    @classmethod
    def rehydrate(
        cls,
        *,
        wb_id: int,
        name: str,
        price: Money,
        sale_price: Money,
        rating: Rating,
        reviews_count: ReviewsCount,
        source_query: str | None = None,
    ) -> Product:
        return cls(
            wb_id=wb_id,
            name=name,
            price=price,
            sale_price=sale_price,
            rating=rating,
            reviews_count=reviews_count,
            source_query=source_query,
        )
