"""Domain tests for the discount policy (pure). RED before T013."""

from decimal import Decimal

from catalog.domain.discount import discount_abs, discount_pct
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount


def _make(price: str, sale: str) -> Product:
    return Product.create(
        wb_id=1,
        name="x",
        price=Money(Decimal(price)),
        sale_price=Money(Decimal(sale)),
        rating=Rating(Decimal("4.0")),
        reviews_count=ReviewsCount(1),
        source_query=None,
    )


def test_discount_abs_is_price_minus_sale():
    assert discount_abs(_make("100", "60")) == Money(Decimal("40.00"))


def test_discount_pct():
    assert discount_pct(_make("100", "60")) == Decimal("40.00")


def test_discount_pct_zero_price_has_no_division_error():
    assert discount_pct(_make("0", "0")) == Decimal("0.00")


def test_no_discount():
    p = _make("50", "50")
    assert discount_abs(p) == Money(Decimal("0.00"))
    assert discount_pct(p) == Decimal("0.00")
