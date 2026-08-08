"""Catalog domain: discount policy (pure functions).

"Discount size" is the absolute ruble difference; the percentage is secondary and
safe when the base price is zero (no division-by-zero). Used by the analytics read
model / charts.
"""

from __future__ import annotations

from decimal import Decimal

from catalog.domain.product import Product
from shared.domain.value_objects import Money

_PCT_QUANT = Decimal("0.01")


def discount_abs(product: Product) -> Money:
    """Absolute discount in rubles (price − sale price); never negative."""
    return product.price - product.sale_price


def discount_pct(product: Product) -> Decimal:
    """Discount as a percentage of the base price; 0 when the price is 0."""
    base = product.price.amount
    if base <= 0:
        return Decimal("0.00")
    diff = base - product.sale_price.amount
    return (diff / base * 100).quantize(_PCT_QUANT)
