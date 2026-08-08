"""Shared domain value objects (pure — no framework, no I/O).

Constructors are strict: they raise ``ValueError`` on invalid input so invalid
state cannot exist in the domain. The ``coerce`` classmethods are the lenient
boundary parsers for dirty Wildberries data (non-numeric / out-of-range values
map to a safe default) and are used by the WB gateway adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

__all__ = ["Money", "Rating", "ReviewsCount"]

_MONEY_QUANT = Decimal("0.01")
_RATING_QUANT = Decimal("0.1")
_RATING_MIN = Decimal("0")
_RATING_MAX = Decimal("5")


def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    # str() keeps float inputs exact enough via their repr; ints/strs pass through.
    return Decimal(str(value))


@dataclass(frozen=True, order=True)
class Money:
    """A non-negative monetary amount in rubles, stored with 2 decimals."""

    amount: Decimal

    def __post_init__(self) -> None:
        amount = _to_decimal(self.amount).quantize(_MONEY_QUANT)
        if amount < 0:
            raise ValueError(f"Money cannot be negative: {amount}")
        object.__setattr__(self, "amount", amount)

    @classmethod
    def from_kopecks(cls, kopecks: int) -> Money:
        """Wildberries prices come in kopecks (×100); normalize to rubles."""
        return cls(Decimal(kopecks) / Decimal(100))

    def __sub__(self, other: Money) -> Money:
        return Money(self.amount - other.amount)


@dataclass(frozen=True, order=True)
class Rating:
    """A product rating in the closed range [0.0, 5.0], one decimal place."""

    value: Decimal

    def __post_init__(self) -> None:
        value = _to_decimal(self.value)
        if value < _RATING_MIN or value > _RATING_MAX:
            raise ValueError(f"Rating must be within [0, 5]: {value}")
        object.__setattr__(self, "value", value.quantize(_RATING_QUANT))

    @classmethod
    def coerce(cls, raw: object) -> Rating:
        """Parse dirty input; non-numeric → 0, out-of-range → clamped to [0, 5]."""
        try:
            value = _to_decimal(raw)
        except (InvalidOperation, ValueError, TypeError):
            return cls(_RATING_MIN)
        clamped = min(_RATING_MAX, max(_RATING_MIN, value))
        return cls(clamped)


@dataclass(frozen=True, order=True)
class ReviewsCount:
    """A non-negative count of reviews."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise ValueError(f"ReviewsCount must be an int: {self.value!r}")
        if self.value < 0:
            raise ValueError(f"ReviewsCount cannot be negative: {self.value}")

    @classmethod
    def coerce(cls, raw: object) -> ReviewsCount:
        """Parse dirty input; non-numeric / negative → 0; floats truncate."""
        try:
            count = int(float(raw))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return cls(0)
        return cls(count if count > 0 else 0)
