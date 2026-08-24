"""Domain events — the cross-context integration seam.

Events are immutable facts published after a successful operation. Contexts react
to them through the event bus, so they stay decoupled and microservice-ready.
Kept minimal and primitive-typed so a future message-bus adapter can serialize
them without domain coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

__all__ = ["DomainEvent", "ProductsCollected", "PriceChanged"]


class DomainEvent:
    """Marker base for all domain events."""


@dataclass(frozen=True)
class ProductsCollected(DomainEvent):
    """Emitted after a parse run upserts products for a query."""

    query: str
    wb_ids: tuple[int, ...]
    collected_count: int
    occurred_at: datetime


@dataclass(frozen=True)
class PriceChanged(DomainEvent):
    """Emitted when a product's sale price differs from the previous snapshot."""

    wb_id: int
    old_sale_price: Decimal
    new_sale_price: Decimal
    occurred_at: datetime
