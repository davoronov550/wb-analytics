"""Notifications application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Observation:
    """A product's current (and previous) sale price to evaluate alerts against."""

    wb_id: int
    query: str | None
    sale_price: Decimal
    previous_sale_price: Decimal | None = None
