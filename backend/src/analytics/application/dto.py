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
