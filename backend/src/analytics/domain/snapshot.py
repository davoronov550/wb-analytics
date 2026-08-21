"""Analytics domain: an append-only price snapshot (pure)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Snapshot:
    wb_id: int
    price: Decimal
    sale_price: Decimal
    rating: Decimal
    captured_at: datetime
